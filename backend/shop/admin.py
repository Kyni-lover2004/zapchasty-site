"""Русская админка: товар, фотографии и характеристики на одной странице."""
from django import forms
from django.contrib import admin
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from .models import Category, Product, ProductPartCounter, Photo, Specification, StoreSettings

admin.site.site_header = 'PartStack · управление магазином'
admin.site.site_title = 'PartStack'
admin.site.index_title = 'Каталог и сотрудники'
admin.site.site_url = '/'

class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 1
    fields = ['preview', 'image', 'position']
    readonly_fields = ['preview']

    @admin.display(description='Предпросмотр')
    def preview(self, obj):
        """Показывает сохранённое фото рядом с загрузкой."""
        return format_html('<img src="{}" width="100" style="max-height:100px;object-fit:contain">', obj.image.url) if obj.image else 'Новое фото'

class SpecificationInline(admin.TabularInline):
    model = Specification
    extra = 1


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ['part']

    def clean(self):
        """Закрепляет очередной номер на время сохранения нового товара."""
        data = super().clean()
        if self.instance._state.adding and not self.errors:
            # Django сохраняет карточку и вложенные формы в одной транзакции.
            counter, _ = ProductPartCounter.objects.select_for_update().get_or_create(pk=1)
            number = counter.get_next_number()
            if number > 9999:
                raise forms.ValidationError('Все артикулы в формате z62-0000 заняты. Нужен более длинный формат.')
            self.instance.part = f'z62-{number:04d}'
        return data


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ['name', 'part', 'category', 'price', 'stock', 'active', 'featured']
    list_display_links = ['name']
    list_editable = ['price', 'active', 'featured']
    search_fields = ['name', 'part', 'device', 'compatibility']
    list_filter = ['active', 'category', 'brand', 'featured']
    list_per_page = 30
    inlines = [PhotoInline, SpecificationInline]
    readonly_fields = ['updated_at', 'stock', 'show_part', 'print_label']
    fieldsets = [
        ('Товар', {'fields': ['name', 'show_part', 'print_label', 'category', 'subtitle', 'description']}),
        ('Цена и наличие', {'fields': ['price', 'old_price', 'stock', 'active', 'featured', 'badge']}),
        ('Совместимость', {'fields': ['brand', 'device', 'compatibility', 'warranty']}),
        ('Дополнительно', {'fields': ['slug', 'updated_at'], 'classes': ['collapse']}),
    ]
    actions = ['hide_products', 'publish_products']

    @admin.display(description='Артикул')
    def show_part(self, product):
        """Показывает текущий артикул или следующий свободный на форме создания."""
        if product.pk:
            return product.part
        counter = ProductPartCounter.objects.filter(pk=1).first() or ProductPartCounter()
        number = counter.get_next_number()
        return f'z62-{number:04d} · присвоится при сохранении' if number <= 9999 else 'Свободных номеров нет.'

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        """Сохраняет актуальный остаток и продвигает счётчик новых товаров."""
        if change:
            obj.stock = Product.objects.select_for_update().values_list('stock', flat=True).get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if not change:
            ProductPartCounter.objects.filter(pk=1).update(next_number=int(obj.part[4:]) + 1)

    @admin.display(description='QR-этикетка')
    def print_label(self, product):
        """Открывает печать после создания карточки."""
        if not product.pk:
            return 'Доступна после сохранения товара.'
        return format_html('<a href="{}">Напечатать этикетку</a>', reverse('warehouse_labels', args=[product.pk]))

    def get_actions(self, request):
        """Оставляет удаление отдельным действием в строке товара."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def get_list_display(self, request):
        """Добавляет удаление рядом с галочкой для пользователей с нужным правом."""
        columns = super().get_list_display(request)
        if self.has_delete_permission(request):
            return ['delete_link', *columns]
        return columns

    @admin.display(description='')
    def delete_link(self, product):
        """Открывает штатную страницу подтверждения удаления товара."""
        url = reverse('admin:shop_product_delete', args=[product.pk])
        return format_html(
            '<a class="product-delete-link" href="{}" aria-label="Удалить товар {}">Удалить</a>',
            url, product.name,
        )

    @admin.action(description='Скрыть выбранные товары с сайта')
    def hide_products(self, request, queryset):
        """Скрывает товары без удаления записей и фото."""
        queryset.update(active=False)

    @admin.action(description='Показать выбранные товары на сайте')
    def publish_products(self, request, queryset):
        """Возвращает товары на витрину."""
        queryset.update(active=True)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ['name']}


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['address', 'hours', 'phone']
    list_display_links = ['address']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
