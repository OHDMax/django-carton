from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.utils.importlib import import_module

from carton import settings as carton_settings


class CartItem(object):
    """
    A cart item, with the associated product, it's quantity and it's price.
    """
    def __init__(self, product, quantity, price):
        self.product = product
        self.quantity = int(quantity)
        self.price = Decimal(str(price))

    def __repr__(self):
        return u'CartItem Object (%s)' % self.product

    def to_dict(self):
        return {
            'product_pk': self.product.pk,
            'quantity': self.quantity,
            'price': str(self.price),
        }

    @property
    def subtotal(self):
        """
        Subtotal for the cart item.
        """
        return self.price * self.quantity


class Cart(object):
    """
    A cart that lives in the session.
    """
    def __init__(self, session, session_key=None):
        self._items_dict = defaultdict(dict)
        self.session = session
        self.session_key = session_key or carton_settings.CART_SESSION_KEY

        # If a cart representation was previously stored in session, then we
        # rebuild the cart object from that serialized representation.
        if self.session_key in self.session:
            cart_representation = self.session[self.session_key]

            for model, items in cart_representation.items():
                Model = self.get_product_model(model)

                products = self.filter_products(Model.objects.all())

                for product in products.filter(pk__in=items.keys()):
                    item = cart_representation[model][str(product.pk)]

                    self._items_dict[model][str(product.pk)] = CartItem(
                        product,
                        item['quantity'],
                        Decimal(item['price']),
                    )

    def __contains__(self, product):
        """
        Checks if the given product is in the cart.
        """
        return product in self.products

    def get_product_model(self, path):
        """
        Takes a full import path and returns the class.
        """
        mod_path, class_name = path.rsplit('.', 1)
        return getattr(import_module(mod_path), class_name)

    def get_product_model_path(self, model):
        """
        Takes a model instance and returns a string of the full
        import path.
        """
        return '.'.join([model.__module__, type(model).__name__])

    def filter_products(self, queryset):
        """
        Applies lookup parameters defined in settings.
        """
        lookup_parameters = getattr(settings, 'CART_PRODUCT_LOOKUP', None)
        if lookup_parameters:
            queryset = queryset.filter(**lookup_parameters)
        return queryset

    def update_session(self):
        """
        Serializes the cart data, saves it to session and marks session as modified.
        """
        self.session[self.session_key] = self.cart_serializable
        self.session.modified = True

    def add(self, product, price=None, quantity=1):
        """
        Adds or creates products in cart. For an existing product,
        the quantity is increased and the price is ignored.
        """
        model = self.get_product_model_path(product)
        quantity = int(quantity)

        if quantity < 1:
            raise ValueError('Quantity must be at least 1 when adding to cart')

        if product in self.products:
            self._items_dict[model][product.pk].quantity += quantity
        else:
            if price is None:
                raise ValueError('Missing price when adding to cart')
            self._items_dict[model][product.pk] = CartItem(product, quantity, price)

        self.update_session()

    def remove(self, product):
        """
        Removes the product.
        """
        model = self.get_product_model_path(product)

        if product in self.products:
            del self._items_dict[model][product.pk]
            self.update_session()

    def remove_single(self, product):
        """
        Removes a single product by decreasing the quantity.
        """
        model = self.get_product_model_path(product)

        if product in self.products:
            if self._items_dict[model][product.pk].quantity <= 1:
                # There's only 1 product left so we drop it
                del self._items_dict[model][product.pk]
            else:
                self._items_dict[model][product.pk].quantity -= 1
            self.update_session()

    def clear(self):
        """
        Removes all items.
        """
        self._items_dict = {}
        self.update_session()

    def set_quantity(self, product, quantity):
        """
        Sets the product's quantity.
        """
        model = self.get_product_model_path(product)
        quantity = int(quantity)

        if quantity < 0:
            raise ValueError('Quantity must be positive when updating cart')

        if product in self.products:
            self._items_dict[model][product.pk].quantity = quantity

            if self._items_dict[model][product.pk].quantity < 1:
                del self._items_dict[model][product.pk]

            self.update_session()

    @property
    def items(self):
        """
        The list of cart items.
        """
        return [i for _ in self._items_dict.values() for i in _.values()]

    @property
    def cart_serializable(self):
        """
        The serializable representation of the cart. For instance:

            {
                'apps.shop.models.Ticket': {
                    '1': {'product_pk': 1, 'quantity': 2, 'price': '9.99'},
                    '2': {'product_pk': 2, 'quantity': 3, 'price': '29.99'},
                },
                'apps.shop.models.Product': {
                    '28': {'product_pk': 28, 'quantity': 1, 'price': '10.00'},
                },
            }

        Note how the product pk serves as a dictionary key.
        """
        cart_representation = defaultdict(dict)

        for item in self.items:
            cart_representation[
                self.get_product_model_path(item.product)
            ][str(item.product.pk)] = item.to_dict()

        return cart_representation

    @property
    def items_serializable(self):
        """
        The list of items formatted for serialization.
        """
        return self.cart_serializable.items()

    @property
    def count(self):
        """
        The number of items in cart, that's the sum of quantities.
        """
        return sum([item.quantity for item in self.items])

    @property
    def unique_count(self):
        """
        The number of unique items in cart, regardless of the quantity.
        """
        return len([i for _ in self._items_dict.values() for i in _.values()])

    @property
    def is_empty(self):
        return self.unique_count == 0

    @property
    def products(self):
        """
        The list of associated products.
        """
        return [item.product for item in self.items]

    @property
    def total(self):
        """
        The total value of all items in the cart.
        """
        return sum([item.subtotal for item in self.items])
