"""Экраны приёмки, учёта и печати этикеток."""
import re
import uuid

import qrcode
from qrcode.image.svg import SvgPathFillImage

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .finance import get_day_entries, get_day_totals, get_month_days
from .models import Expense, Product, Receipt, ReceiptLine, Sale, StockMovement
from .stock import (MAX_STOCK, StockError, adjust_stock, apply_receipt_action, apply_sale_action,
                    find_product, get_refundable_lines, refund_sale)

WAREHOUSE_PERMISSION = 'shop.operate_stock'


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ['number', 'supplier']


class CodeForm(forms.Form):
    code = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=1, max_value=MAX_STOCK)


class LineForm(forms.Form):
    line = forms.IntegerField(min_value=1, max_value=2**63 - 1)


class UndoScanForm(LineForm):
    quantity = forms.IntegerField(min_value=1, max_value=MAX_STOCK, required=False)


class PostReceiptForm(forms.Form):
    accept_difference = forms.BooleanField(required=False)


class SaleScanForm(forms.Form):
    code = forms.CharField(max_length=100)
    operation_id = forms.UUIDField()


class SaleUndoForm(LineForm):
    operation_id = forms.UUIDField()


class SaleCloseForm(forms.Form):
    payment_method = forms.ChoiceField(
        label='Оплата', choices=[('', 'Не указано'), *Sale.Payment.choices], required=False,
    )


class SaleRefundForm(forms.Form):
    operation_id = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, lines, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = []
        for line in lines:
            available = line.quantity - line.returned
            name = f'quantity_{line.pk}'
            self.fields[name] = forms.IntegerField(
                label=f'Вернуть {line.part}', required=False, min_value=0, max_value=available,
                widget=forms.NumberInput(attrs={'placeholder': '0', 'aria-label': f'Вернуть {line.part}'}),
            )
            self.rows.append((line, available, self[name]))

    def get_quantities(self):
        """Возвращает выбранные строки и количества."""
        return {line.pk: self.cleaned_data[field.name] for line, _, field in self.rows
                if self.cleaned_data[field.name]}


class ReportDayForm(forms.Form):
    day = forms.DateField(label='Дата отчёта', widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))


class ExpenseForm(forms.ModelForm):
    entry_id = forms.UUIDField(widget=forms.HiddenInput)

    class Meta:
        model = Expense
        fields = ['spent_at', 'category', 'description', 'amount']
        widgets = {'spent_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}


class AdjustmentForm(forms.Form):
    kind = forms.ChoiceField(
        label='Операция',
        choices=[(kind.value, kind.label) for kind in (
            StockMovement.Kind.ISSUE, StockMovement.Kind.WRITE_OFF, StockMovement.Kind.COUNT,
        )],
    )
    quantity = forms.IntegerField(label='Количество, шт.', min_value=0, max_value=MAX_STOCK)
    reason = forms.CharField(label='Причина или номер заказа', max_length=250)
    operation_id = forms.UUIDField(widget=forms.HiddenInput)
    previous_balance = forms.IntegerField(min_value=0, max_value=MAX_STOCK, widget=forms.HiddenInput)

    def clean(self):
        """Разрешает ноль только для фактического запаса при пересчёте."""
        data = super().clean()
        if data.get('quantity') == 0 and data.get('kind') != StockMovement.Kind.COUNT:
            self.add_error('quantity', 'Укажите хотя бы одну штуку.')
        return data


class PrintForm(forms.Form):
    copies = forms.IntegerField(label='Количество этикеток', min_value=1, max_value=500)


def render_warehouse(request, template, title, **context):
    """Использует общую шапку админки и навигацию склада."""
    return render(request, f'shop/warehouse/{template}.html', {
        **admin.site.each_context(request), 'title': title, 'is_nav_sidebar_enabled': False, **context,
    })


def search_products(query):
    """Ищет по названию, комплектации, модели или артикулу."""
    if not query:
        return Product.objects.all()
    if len(query) <= 100:
        exact = find_product(query)
        if exact:
            return Product.objects.filter(pk=exact.pk)
    return Product.objects.filter(
        Q(part__icontains=query) | Q(name__icontains=query)
        | Q(device__icontains=query) | Q(subtitle__icontains=query),
    )


@require_http_methods(['GET', 'POST'])
def list_receipts(request):
    """Открывает журнал накладных и создаёт новые черновики."""
    form = ReceiptForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        return redirect('warehouse_receipt', pk=form.save().pk)
    receipts = Paginator(Receipt.objects.order_by('-id'), 30).get_page(request.GET.get('page'))
    return render_warehouse(request, 'receipts', 'Приёмка товара', form=form, page=receipts)


@require_http_methods(['GET', 'POST'])
def show_receipt(request, pk):
    """Принимает сканы, правки накладной и подтверждение прихода."""
    receipt = get_object_or_404(Receipt, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        form_class = {
            'add': CodeForm, 'scan': CodeForm, 'undo': UndoScanForm,
            'remove': LineForm, 'post': PostReceiptForm,
        }.get(action)
        if form_class is None:
            return HttpResponse('Неизвестная операция.', status=400)
        form = form_class(request.POST)
        if form.is_valid():
            try:
                message = apply_receipt_action(pk, request.user, action, form.cleaned_data)
            except StockError as error:
                messages.error(request, str(error))
            else:
                if action == 'scan' and 'В накладной меньше' in message:
                    messages.warning(request, message)
                else:
                    messages.success(request, message)
        else:
            messages.error(request, 'Проверьте код и количество в форме.')
        return redirect('warehouse_receipt', pk=pk)

    lines = list(receipt.lines.select_related('product').order_by('id'))
    return render_warehouse(
        request, 'receipt', f'Накладная № {receipt.number}', receipt=receipt, lines=lines,
        differs=any(line.expected != line.received for line in lines),
    )


@require_GET
def suggest_products(request):
    """Возвращает первые совпадения для выбора товара в накладной."""
    query = request.GET.get('q', '').strip()[:250]
    products = search_products(query).order_by('name', 'part')[:15] if query else []
    return JsonResponse({'products': [
        {'part': product.part, 'name': product.name, 'subtitle': product.subtitle} for product in products
    ]})


@require_GET
def list_stock(request):
    """Показывает остатки и открывает карточку по точному скану."""
    query = request.GET.get('q', '').strip()[:250]
    exact = find_product(query) if 0 < len(query) <= 100 else None
    if exact:
        return redirect('warehouse_product', pk=exact.pk)
    products = search_products(query).order_by('name', 'part')
    page = Paginator(products, 50).get_page(request.GET.get('page'))
    return render_warehouse(request, 'stock', 'Учёт остатков', page=page, query=query)


@require_http_methods(['GET', 'POST'])
def show_product(request, pk):
    """Показывает движение товара и проводит выдачу, списание или пересчёт."""
    product = get_object_or_404(Product, pk=pk)
    form = AdjustmentForm(
        request.POST if request.method == 'POST' else None,
        initial={'operation_id': uuid.uuid4(), 'previous_balance': product.stock},
    )
    if request.method == 'POST' and form.is_valid():
        try:
            adjust_stock(pk, request.user, **form.cleaned_data)
        except StockError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, 'Движение записано. Остаток обновлён.')
            return redirect('warehouse_product', pk=pk)

    history = StockMovement.objects.filter(product=product).select_related('receipt', 'sale')
    page = Paginator(history, 30).get_page(request.GET.get('page'))
    return render_warehouse(request, 'product', product.name, product=product, form=form, page=page)


@require_http_methods(['GET', 'POST'])
def list_sales(request):
    """Показывает заказы и создаёт новый заказ с очередным номером."""
    if request.method == 'POST':
        return redirect('warehouse_sale', pk=Sale.objects.create().pk)
    page = Paginator(Sale.objects.order_by('-id'), 30).get_page(request.GET.get('page'))
    return render_warehouse(request, 'sales', 'Реализация товара', page=page,
                            totals=get_day_totals(timezone.localdate()))


@require_http_methods(['GET', 'POST'])
def show_sales_report(request):
    """Открывает сводку за месяц и журнал за день, сохраняет расходы."""
    day_form = ReportDayForm(request.GET if 'day' in request.GET else None,
                             initial={'day': timezone.localdate()})
    day = day_form.cleaned_data['day'] if day_form.is_valid() else timezone.localdate()
    expense_form = ExpenseForm(
        request.POST if request.method == 'POST' else None,
        initial={'spent_at': timezone.now(), 'entry_id': uuid.uuid4()},
    )
    if request.method == 'POST' and expense_form.is_valid():
        data = expense_form.cleaned_data.copy()
        entry_id = data.pop('entry_id')
        expense, created = Expense.objects.get_or_create(
            pk=entry_id, defaults={**data, 'employee_name': request.user.get_username()},
        )
        if created:
            messages.success(request, 'Расход записан.')
        else:
            messages.info(request, 'Этот расход уже записан.')
        return redirect(f'{request.path}?day={timezone.localdate(expense.spent_at).isoformat()}#report-day')
    return render_warehouse(
        request, 'sales_report', 'Отчёт по деньгам', day=day, day_form=day_form,
        expense_form=expense_form, totals=get_day_totals(day), days=get_month_days(day),
        entries=get_day_entries(day),
    )


def get_sale_items(sale):
    """Собирает позиции и итоги в едином виде для заказа и накладной."""
    lines = list(sale.lines.order_by('id'))
    return {'sale': sale, 'lines': lines, 'units': sum(line.quantity for line in lines),
            'total': sum(line.total for line in lines)}


@require_http_methods(['GET', 'POST'])
def show_returns(request):
    """Ищет завершённый заказ и проводит частичный или полный возврат."""
    order = request.GET.get('order', '').strip().lower()[:24]
    sale = None
    lookup_error = ''
    if order:
        match = re.fullmatch(r'(?:r62-)?([0-9]{1,19})', order)
        if match:
            sale = Sale.objects.filter(pk=int(match[1]) + 1).first()
        if not sale:
            lookup_error = 'Заказ с таким номером не найден.'
        elif not sale.closed_at:
            lookup_error = 'Возврат доступен после завершения заказа.'

    form = None
    if sale and not lookup_error:
        form = SaleRefundForm(
            get_refundable_lines(sale), request.POST if request.method == 'POST' else None,
            initial={'operation_id': uuid.uuid4()},
        )
        if request.method == 'POST' and form.is_valid():
            try:
                total = refund_sale(sale.pk, request.user, form.cleaned_data['operation_id'], form.get_quantities())
            except StockError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, f'Товар возвращён на склад. Сумма возврата {total} ₽.')
                return redirect(f'{request.path}?order={sale.number}')
    return render_warehouse(
        request, 'returns', 'Возвраты', order=order, sale=sale, lookup_error=lookup_error, form=form,
        can_refund=form and any(available for _, available, _ in form.rows),
    )


@require_http_methods(['GET', 'POST'])
def show_sale(request, pk):
    """Применяет операции по заказу и показывает актуальное количество."""
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        form_class = {'scan': SaleScanForm, 'undo': SaleUndoForm, 'close': SaleCloseForm}.get(action)
        if not form_class:
            return HttpResponse('Неизвестная операция.', status=400)
        form = form_class(request.POST)
        if form.is_valid():
            try:
                result = apply_sale_action(pk, request.user, action, form.cleaned_data)
            except StockError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, result)
        else:
            messages.error(request, 'Проверьте код или обновите страницу заказа.')
        return redirect('warehouse_sale', pk=pk)
    return render_warehouse(request, 'sale', f'Заказ {sale.number}',
                            operation_id=str(uuid.uuid4()), close_form=SaleCloseForm(), **get_sale_items(sale))


@require_GET
def print_sale(request, pk):
    """Выводит накладную для печати на A4."""
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'shop/warehouse/sale_print.html', get_sale_items(sale))


def require_label_access(request):
    """Разрешает печать складским сотрудникам и редакторам карточек."""
    if not (request.user.has_perm(WAREHOUSE_PERMISSION) or request.user.has_perm('shop.view_product')
            or request.user.has_perm('shop.change_product')):
        raise PermissionDenied


@require_GET
def print_labels(request, pk):
    """Готовит страницу печати для карточки или строки накладной."""
    require_label_access(request)
    product = get_object_or_404(Product, pk=pk)
    line = None
    if request.GET.get('line'):
        line_form = LineForm(request.GET)
        if not line_form.is_valid():
            return HttpResponse('Некорректная строка накладной.', status=400)
        line = get_object_or_404(ReceiptLine, pk=line_form.cleaned_data['line'], product=product)
    form = PrintForm({'copies': request.GET.get('copies', min(line.expected, 500) if line else 1)})
    copies = range(form.cleaned_data['copies']) if form.is_valid() else ()
    return render_warehouse(request, 'labels', 'Печать этикеток', form=form, product=product, line=line, copies=copies)


@require_GET
def show_qr(request, pk):
    """Рисует QR локально, без внешнего сервиса."""
    require_label_access(request)
    product = get_object_or_404(Product, pk=pk)
    code = qrcode.QRCode(box_size=10, border=4)
    code.add_data(product.qr_code)
    drawing = code.make_image(image_factory=SvgPathFillImage)
    return HttpResponse(drawing.to_string(), content_type='image/svg+xml')


def staff_stock_view(view):
    """Требует вход сотрудника и разрешение на проведение движений."""
    def check_permission(request, *args, **kwargs):
        if not request.user.has_perm(WAREHOUSE_PERMISSION):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return admin.site.admin_view(check_permission)


urlpatterns = [
    path('', staff_stock_view(list_receipts), name='warehouse_receipts'),
    path('receipts/<int:pk>/', staff_stock_view(show_receipt), name='warehouse_receipt'),
    path('products/search/', staff_stock_view(suggest_products), name='warehouse_suggest'),
    path('stock/', staff_stock_view(list_stock), name='warehouse_stock'),
    path('stock/<int:pk>/', staff_stock_view(show_product), name='warehouse_product'),
    path('sales/', staff_stock_view(list_sales), name='warehouse_sales'),
    path('sales/report/', staff_stock_view(show_sales_report), name='warehouse_sales_report'),
    path('returns/', staff_stock_view(show_returns), name='warehouse_returns'),
    path('sales/<int:pk>/', staff_stock_view(show_sale), name='warehouse_sale'),
    path('sales/<int:pk>/print/', staff_stock_view(print_sale), name='warehouse_sale_print'),
    path('labels/<int:pk>/', admin.site.admin_view(print_labels), name='warehouse_labels'),
    path('labels/<int:pk>/qr/', admin.site.admin_view(show_qr), name='warehouse_qr'),
]
