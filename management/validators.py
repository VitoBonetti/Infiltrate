from django.core.exceptions import ValidationError


def validate_file_size(file):
    max_size_kb = 2048  # 2 MB limit
    if file.size > max_size_kb * 1024:
        raise ValidationError(f"File size cannot exceed {max_size_kb / 1024} MB.")


def validate_image_magic_bytes(file):
    """
    Validates that the uploaded image file genuinely matches JPEG, PNG, or GIF signatures.
    """
    # Read the first 8 bytes
    header = file.read(8)
    file.seek(0)  # Reset file pointer so Django/Pillow can read it later

    # JPEG: starts with ff d8 ff
    # PNG: starts with 89 50 4e 47 0d 0a 1a 0a
    # GIF: starts with 47 49 46 38 (GIF8)

    if header.startswith(b'\xff\xd8\xff'):
        return
    elif header.startswith(b'\x89PNG\r\n\x1a\n'):
        return
    elif header.startswith(b'GIF8'):
        return

    raise ValidationError("Invalid file content. Only genuine JPEG, PNG, and GIF files are allowed.")


def validate_excel_magic_bytes(file):
    """
    Validates that the file is genuinely a ZIP archive (which .xlsx files are).
    """
    header = file.read(4)
    file.seek(0)  # Reset file pointer

    # .xlsx files are ZIP archives, so they start with PK\x03\x04
    if not header.startswith(b'PK\x03\x04'):
        raise ValidationError("Invalid Excel file. The file content does not match a valid .xlsx archive.")