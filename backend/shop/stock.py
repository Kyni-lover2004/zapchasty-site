"""Проведение приёмки и других движений с блокировкой остатков."""
import re

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Product, Receipt, ReceiptLine, Sale, SaleRefund, SaleRefundLine, StockMovement

MAX_STOCK = 2_147_483_647


class StockError(ValueError):
    pass


def find_product(code: str):
    """Находит карточку по QR или по точному артикулу."""
    code = code.strip()
    if re.fullmatch(r'Z62:[1-9][0-9]{0,18}', code):
        product_id = int(code[4:])
        if product_id <= 2**63 - 1:
            return Product.objects.filter(pk=product_id).first()
    return Product.objects.filter(part=code).first()


def record_movement(product, employee, kind, balance, reason='', receipt=None, operation_id=None, sale=None):
    """Меняет остаток заблокированного товара и записывает движение."""
    if not 0 <= balance <= MAX_STOCK:
        raise StockError('После операции остаток должен быть от 0 до 2 147 483 647 шт.')
    previous = product.stock
    if previous != balance:
        product.stock = balance
        product.save(update_fields=['stock', 'updated_at'])
    StockMovement.objects.create(
        product=product, receipt=receipt, sale=sale, employee=employee, employee_name=employee.get_username(),
        kind=kind, change=balance - previous, balance=balance, reason=reason, operation_id=operation_id,
    )


@transaction.atomic
def apply_receipt_action(receipt_id, employee, action, data):
    """Сохраняет строку или сверку, либо один раз проводит накладную."""
    receipt = Receipt.objects.select_for_update().get(pk=receipt_id)
    if receipt.posted_at:
        raise StockError('Эта накладная уже проведена.')
    if action == 'post':
        post_receipt(receipt, employee, data['accept_difference'])
        return 'Накладная проведена. Остатки обновлены.'

    if action in ('remove', 'undo'):
        line = receipt.lines.select_related('product').filter(pk=data['line']).first()
        if not line:
            raise StockError('Строка не найдена в этой накладной.')
        if action == 'undo':
            quantity = data['quantity'] or 1
            if line.received < quantity:
                raise StockError(f'По этой строке принято только {line.received} шт.')
            line.received -= quantity
            line.save(update_fields=['received'])
            return f'{line.product.part} · принято {line.received} из {line.expected}.'
        if line.received:
            raise StockError('Сначала отмените принятые по строке штуки.')
        line.delete()
        return 'Позиция убрана из накладной.'

    product = find_product(data['code'])
    if not product:
        raise StockError(f'Код или артикул «{data["code"]}» не найден в каталоге.')
    quantity = data['quantity']
    if action == 'add':
        ReceiptLine.objects.update_or_create(receipt=receipt, product=product, defaults={'expected': quantity})
        return f'{product.part} · по накладной {quantity} шт.'

    line = receipt.lines.filter(product=product).first()
    if not line:
        raise StockError(f'{product.part} отсутствует в этой накладной.')
    if line.received + quantity > MAX_STOCK:
        raise StockError('Превышено допустимое количество для строки.')
    line.received += quantity
    line.save(update_fields=['received'])
    result = f'{product.part} · принято {line.received} из {line.expected}.'
    if line.received > line.expected:
        result += ' В накладной меньше, чем принято.'
    return result


def post_receipt(receipt, employee, accept_difference):
    """Подтверждает фактический приход, сохраняя ожидаемые количества."""
    lines = list(receipt.lines.order_by('product_id'))
    if not lines:
        raise StockError('Добавьте хотя бы одну позицию.')
    if not accept_difference and any(line.received != line.expected for line in lines):
        raise StockError('Есть расхождения. Проверьте счётчики и отметьте подтверждение расхождений.')

    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[line.product_id for line in lines if line.received],
        ).order_by('pk')
    }
    for line in lines:
        if line.received:
            product = products[line.product_id]
            record_movement(product, employee, StockMovement.Kind.RECEIPT,
                            product.stock + line.received, receipt=receipt)
    receipt.posted_at = timezone.now()
    receipt.save(update_fields=['posted_at'])


@transaction.atomic
def adjust_stock(product_id, employee, kind, quantity, reason, operation_id, previous_balance):
    """Проводит ручное движение один раз, даже при повторной отправке формы."""
    product = Product.objects.select_for_update().get(pk=product_id)
    if StockMovement.objects.filter(product=product, operation_id=operation_id).exists():
        raise StockError('Эта операция уже проведена. Откройте форму заново для нового движения.')
    if kind == StockMovement.Kind.COUNT and previous_balance != product.stock:
        raise StockError('Остаток изменился. Обновите страницу и проверьте количество перед пересчётом.')
    balance = quantity if kind == StockMovement.Kind.COUNT else product.stock - quantity
    if balance < 0:
        raise StockError(f'На складе только {product.stock} шт.')
    record_movement(product, employee, kind, balance, reason, operation_id=operation_id)


@transaction.atomic
def apply_sale_action(sale_id, employee, action, data):
    """Меняет заказ и складской остаток в одной транзакции."""
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if sale.closed_at:
        raise StockError('Заказ уже завершён.')
    if action == 'close':
        if not sale.lines.exists():
            raise StockError('Добавьте в заказ хотя бы один товар.')
        sale.closed_at = timezone.now()
        sale.payment_method = data['payment_method']
        sale.cashier_name = employee.get_full_name() or employee.get_username()
        sale.save(update_fields=['closed_at', 'payment_method', 'cashier_name'])
        return 'Заказ завершён.'

    operation_id = data['operation_id']
    if sale.movements.filter(operation_id=operation_id).exists():
        raise StockError('Эта операция уже учтена.')

    if action == 'undo':
        line = sale.lines.filter(pk=data['line']).first()
        if not line:
            raise StockError('Позиции уже нет в заказе.')
        product = Product.objects.select_for_update().get(pk=line.product_id)
        record_movement(product, employee, StockMovement.Kind.SALE_RETURN,
                        product.stock + 1, operation_id=operation_id, sale=sale)
        if line.quantity == 1:
            line.delete()
        else:
            line.quantity -= 1
            line.save(update_fields=['quantity'])
        return f'{product.part} · 1 шт. возвращена в остаток.'

    match = find_product(data['code'])
    if not match:
        raise StockError('QR-код или артикул не найден.')
    product = Product.objects.select_for_update().filter(pk=match.pk).first()
    if not product or not product.stock:
        raise StockError(f'{match.part} · товара нет в наличии.')
    line, created = sale.lines.get_or_create(product=product, defaults={
        'part': product.part, 'name': product.name, 'subtitle': product.subtitle, 'price': product.price,
    })
    if not created:
        if line.quantity == MAX_STOCK:
            raise StockError('Достигнут предел количества для этой позиции.')
        line.quantity += 1
        line.save(update_fields=['quantity'])
    record_movement(product, employee, StockMovement.Kind.ISSUE,
                    product.stock - 1, operation_id=operation_id, sale=sale)
    return f'{line.part} · в заказе {line.quantity} шт., на складе {product.stock} шт.'


def get_refundable_lines(sale):
    """Возвращает строки заказа с количеством ранее возвращённых единиц."""
    return sale.lines.annotate(returned=Sum('refund_lines__quantity', default=0)).order_by('id')


@transaction.atomic
def refund_sale(sale_id, employee, operation_id, quantities):
    """Проводит возврат денег и товара одной операцией."""
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if not sale.closed_at:
        raise StockError('Возврат доступен для завершённого заказа.')
    if sale.refunds.filter(pk=operation_id).exists():
        raise StockError('Этот возврат уже проведён.')

    lines = {line.pk: line for line in get_refundable_lines(sale)}
    if not quantities or not quantities.keys() <= lines.keys():
        raise StockError('Выберите хотя бы одну позицию из заказа.')
    for line_id, quantity in quantities.items():
        line = lines[line_id]
        if not 0 < quantity <= line.quantity - line.returned:
            raise StockError(f'{line.part} · доступно к возврату {line.quantity - line.returned} шт.')

    products = {
        product.pk: product for product in Product.objects.select_for_update().filter(
            pk__in=[lines[line_id].product_id for line_id in quantities],
        ).order_by('pk')
    }
    refund, created = SaleRefund.objects.get_or_create(
        pk=operation_id, defaults={'sale': sale, 'employee_name': employee.get_username()},
    )
    if not created:
        raise StockError('Этот возврат уже проведён.')
    total = 0
    for line_id, quantity in quantities.items():
        line = lines[line_id]
        product = products[line.product_id]
        SaleRefundLine.objects.create(refund=refund, sale_line=line, quantity=quantity)
        record_movement(product, employee, StockMovement.Kind.SALE_RETURN,
                        product.stock + quantity, reason='Возврат покупателя', sale=sale)
        total += line.price * quantity
    return total
