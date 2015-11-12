from django.db import models


class Product(models.Model):
    custom_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    price = models.FloatField()

    def __str__(self):
        return self.name


class Ticket(models.Model):
    custom_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    price = models.FloatField()

    def __str__(self):
        return self.name
