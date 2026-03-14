from django.db import models
import uuid as _uuid


class Tags(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True)
    tag = models.CharField(max_length=100, unique=True)
    text_color = models.CharField(max_length=7, blank=True, null=True, default='#FFFFFF')
    background_color = models.CharField(max_length=7, blank=True, null=True, default='#0C2B4E')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tag


class Flags(models.Model):

    CATEGORIES_CHOICES = [
        ('Remediation KPI', 'Remediation KPI'),
        ('Coverage KPI', 'Coverage KPI'),
        ('Legacy KPI', 'Legacy KPI'),
        ('High Priority', 'High Priority'),
        ('Medium Priority', 'Medium Priority'),
        ('Low Priority', 'Low Priority'),
    ]

    CATEGORY_COLORS = {
        'Remediation KPI': ('#280905', '#EA7B7B'),
        'Coverage KPI': ('#FFFFFF', '#0C2C55'),
        'Legacy KPI': ('#280905', '#ED985F'),
        'High Priority': ('#FFFFFF', '#C00707'),
        'Medium Priority': ('#280905', '#F8843F'),
        'Low Priority': ('#280905', '#FFF19B'),
    }

    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True)
    flag = models.CharField(max_length=100, unique=True)
    categories = models.CharField(max_length=80, choices=CATEGORIES_CHOICES)
    text_color = models.CharField(max_length=7, blank=True, null=True)
    background_color = models.CharField(max_length=7, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # assign colors based on the chosen category
        if self.categories in self.CATEGORY_COLORS:
            # overwrite the colors with the standard choices
            self.text_color = self.CATEGORY_COLORS[self.categories][0]
            self.background_color = self.CATEGORY_COLORS[self.categories][1]

        super().save(*args, **kwargs)

    def __str__(self):
        return self.flag
