from django.db import models
from django.core.files.base import ContentFile
import uuid as _uuid
from management.validators import validate_file_size, validate_image_magic_bytes
from io import BytesIO
from PIL import Image
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os


class Market(models.Model):
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True, primary_key=True)
    region = models.ForeignKey("regions.Regions", on_delete=models.CASCADE, related_name="markets")
    market = models.CharField(max_length=120)
    code = models.CharField(max_length=15, blank=True, null=True)
    language = models.CharField(max_length=15, blank=True, null=True, default="English")
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    key_market = models.BooleanField(default=False)
    flag_icons = models.ImageField(blank=True, null=True, upload_to="market_icons", validators=[validate_file_size, validate_image_magic_bytes])
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)


    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["region", "market"], name="uniq_market_per_region")
        ]

    def __str__(self):
        return f"{self.region} / {self.market}"

    def save(self, *args, **kwargs):
        if self.flag_icons and not self.flag_icons._committed:
            try:
                # Open the image with Pillow
                img = Image.open(self.flag_icons)

                # Check if it has EXIF data (mostly applies to JPEGs/TIFFs)
                if img.getexif():
                    # Safest way to strip all metadata is to copy the raw pixel data into a brand new image
                    data = list(img.getdata())
                    clean_img = Image.new(img.mode, img.size)
                    clean_img.putdata(data)

                    # Save the clean image to memory
                    output = BytesIO()
                    # Default to PNG to preserve transparency if format is missing
                    img_format = img.format if img.format else 'PNG'
                    clean_img.save(output, format=img_format)

                    # Overwrite the uploaded file with our clean, EXIF-free version
                    self.flag_icons.save(self.flag_icons.name, ContentFile(output.getvalue()), save=False)
                else:
                    self.flag_icons.seek(0)

            except Exception as e:
                # If Pillow fails (e.g., corrupted file),
                self.flag_icons.seek(0)

        super().save(*args, **kwargs)


@receiver(post_delete, sender=Market)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes the flag icon from the filesystem
    when the corresponding Market object is deleted.
    """
    if instance.flag_icons:
        if os.path.isfile(instance.flag_icons.path):
            os.remove(instance.flag_icons.path)

@receiver(pre_save, sender=Market)
def auto_delete_file_on_change(sender, instance, **kwargs):
    """
    Deletes the old flag icon from the filesystem
    when the Market object is updated with a new file,
    or when the file is cleared.
    """
    if not instance.pk:
        return # This is a new object, nothing to delete

    try:
        old_market = Market.objects.get(pk=instance.pk)
        old_file = old_market.flag_icons
    except Market.DoesNotExist:
        return

    new_file = instance.flag_icons

    # If the file has changed (or was cleared)
    if not old_file == new_file:
        if old_file and os.path.isfile(old_file.path):
            os.remove(old_file.path)
