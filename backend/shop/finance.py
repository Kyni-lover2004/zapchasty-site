"""Сводка по завершённым продажам и зарегистрированным расходам."""
from calendar import monthrange

from django.db.models import BigIntegerField, F, Sum
from django.db.models.functions import Cast, TruncDate

from .models import Expense, Sale, SaleLine, SaleRefund, SaleRefundLine


def get_day_totals(day):
    """Возвращает выручку, возвраты и расходы за местную календарную дату."""
    line_amount = Cast('price', BigIntegerField()) * F('quantity')
    revenue = SaleLine.objects.filter(sale__closed_at__date=day).aggregate(
        total=Sum(line_amount, default=0),
    )['total']
    expenses = Expense.objects.filter(spent_at__date=day).aggregate(total=Sum('amount', default=0))['total']
    refunds = SaleRefundLine.objects.filter(refund__created_at__date=day).aggregate(
        total=Sum(Cast('sale_line__price', BigIntegerField()) * F('quantity'), default=0),
    )['total']
    return {'revenue': revenue, 'expenses': expenses, 'refunds': refunds, 'balance': revenue - expenses - refunds}


def get_month_days(day):
    """Группирует операции по дням выбранного месяца."""
    first = day.replace(day=1)
    last = day.replace(day=monthrange(day.year, day.month)[1])
    line_amount = Cast('price', BigIntegerField()) * F('quantity')
    sales = SaleLine.objects.filter(sale__closed_at__date__range=(first, last)).order_by().values(
        day=TruncDate('sale__closed_at'),
    ).annotate(total=Sum(line_amount))
    expenses = Expense.objects.filter(spent_at__date__range=(first, last)).order_by().values(
        day=TruncDate('spent_at'),
    ).annotate(total=Sum('amount'))
    refunds = SaleRefundLine.objects.filter(refund__created_at__date__range=(first, last)).order_by().values(
        day=TruncDate('refund__created_at'),
    ).annotate(total=Sum(Cast('sale_line__price', BigIntegerField()) * F('quantity')))
    revenue_by_day = {row['day']: row['total'] for row in sales}
    expenses_by_day = {row['day']: row['total'] for row in expenses}
    refunds_by_day = {row['day']: row['total'] for row in refunds}
    days = sorted(revenue_by_day.keys() | expenses_by_day.keys() | refunds_by_day.keys() | {day}, reverse=True)
    rows = []
    for date in days:
        revenue = revenue_by_day.get(date, 0)
        expense = expenses_by_day.get(date, 0)
        refund = refunds_by_day.get(date, 0)
        rows.append({'day': date, 'revenue': revenue, 'expenses': expense, 'refunds': refund,
                     'balance': revenue - expense - refund})
    return rows


def get_day_entries(day):
    """Собирает продажи и расходы в хронологический журнал."""
    line_amount = Cast('lines__price', BigIntegerField()) * F('lines__quantity')
    sales = Sale.objects.filter(closed_at__date=day).annotate(amount=Sum(line_amount, default=0))
    expenses = Expense.objects.filter(spent_at__date=day)
    refunds = SaleRefund.objects.filter(created_at__date=day).select_related('sale').annotate(
        amount=Sum(Cast('lines__sale_line__price', BigIntegerField()) * F('lines__quantity'), default=0),
    )
    entries = [{'time': sale.closed_at, 'sale': sale, 'amount': sale.amount} for sale in sales]
    entries.extend({'time': expense.spent_at, 'expense': expense, 'amount': expense.amount} for expense in expenses)
    entries.extend({'time': refund.created_at, 'refund': refund, 'amount': refund.amount} for refund in refunds)
    return sorted(entries, key=lambda entry: entry['time'], reverse=True)
