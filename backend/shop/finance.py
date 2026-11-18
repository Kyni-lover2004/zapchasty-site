"""Сводка по завершённым продажам и зарегистрированным расходам."""
from calendar import monthrange

from django.db.models import BigIntegerField, F, Sum
from django.db.models.functions import Cast, TruncDate

from .models import Expense, Sale, SaleLine, SaleRefund, SaleRefundLine


def make_totals(amounts):
    """Возвращает суммы операций и итог после расходов и возвратов."""
    revenue = amounts.get('revenue', 0)
    expenses = amounts.get('expenses', 0)
    refunds = amounts.get('refunds', 0)
    return {'revenue': revenue, 'expenses': expenses, 'refunds': refunds,
            'balance': revenue - expenses - refunds}


def collect_daily_amounts(first, last, by_payment=False):
    """Суммирует операции по местным датам и при необходимости по способам оплаты."""
    sources = [
        ('revenue', SaleLine.objects.all(), 'sale__closed_at', 'sale__payment_method',
         Cast('price', BigIntegerField()) * F('quantity')),
        ('expenses', Expense.objects.all(), 'spent_at', 'payment_method', F('amount')),
        ('refunds', SaleRefundLine.objects.all(), 'refund__created_at', 'refund__sale__payment_method',
         Cast('sale_line__price', BigIntegerField()) * F('quantity')),
    ]
    daily = {}
    for operation, source, timestamp, payment, amount in sources:
        rows = source.filter(**{f'{timestamp}__date__range': (first, last)}).order_by()
        groups = {'day': TruncDate(timestamp)}
        if by_payment:
            groups['payment'] = F(payment)
        for row in rows.values(**groups).annotate(total=Sum(amount)):
            key = (row['day'], row['payment']) if by_payment else row['day']
            daily.setdefault(key, {})[operation] = row['total']
    return daily


def get_day_totals(day):
    """Возвращает общие суммы и разбивку за выбранный день."""
    totals_by_payment = {payment: amounts for (_, payment), amounts in collect_daily_amounts(day, day, by_payment=True).items()}
    totals = make_totals({
        operation: sum(amounts.get(operation, 0) for amounts in totals_by_payment.values())
        for operation in ('revenue', 'expenses', 'refunds')
    })
    methods = [Sale.Payment.CASH, Sale.Payment.CARD]
    if Sale.Payment.TRANSFER in totals_by_payment:
        methods.append(Sale.Payment.TRANSFER)
    totals['payments'] = [
        {'label': method.label, **make_totals(totals_by_payment.get(method, {}))}
        for method in methods
    ]
    if '' in totals_by_payment:
        totals['payments'].append({'label': 'Не указан', **make_totals(totals_by_payment[''])})
    return totals


def get_month_days(day):
    """Группирует операции по дням выбранного месяца."""
    first = day.replace(day=1)
    last = day.replace(day=monthrange(day.year, day.month)[1])
    daily = collect_daily_amounts(first, last)
    return [{'day': date, **make_totals(daily.get(date, {}))}
            for date in sorted(daily.keys() | {day}, reverse=True)]


def get_day_entries(day):
    """Собирает продажи и расходы в хронологический журнал."""
    line_amount = Cast('lines__price', BigIntegerField()) * F('lines__quantity')
    sales = Sale.objects.filter(closed_at__date=day).annotate(amount=Sum(line_amount, default=0))
    expenses = Expense.objects.filter(spent_at__date=day)
    refunds = SaleRefund.objects.filter(created_at__date=day).select_related('sale').annotate(
        amount=Sum(Cast('lines__sale_line__price', BigIntegerField()) * F('lines__quantity'), default=0),
    )
    entries = [{'time': sale.closed_at, 'sale': sale, 'amount': sale.amount,
                'payment': sale.get_payment_method_display()} for sale in sales]
    entries.extend({'time': expense.spent_at, 'expense': expense, 'amount': expense.amount,
                    'payment': expense.get_payment_method_display()} for expense in expenses)
    entries.extend({'time': refund.created_at, 'refund': refund, 'amount': refund.amount,
                    'payment': refund.sale.get_payment_method_display()} for refund in refunds)
    return sorted(entries, key=lambda entry: entry['time'], reverse=True)
