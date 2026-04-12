import os
import django
import urllib.request
import urllib.error

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qrproject.settings')
django.setup()
from django.conf import settings
settings.AWS_S3_ENDPOINT_URL = f"https://s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com"


from qrapp.models import Person

try:
    p = Person.objects.get(person_id='100024')
    url = p.qr_code.url
    print("URL:", url)
    
    # Try fetching the URL
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    print("Status:", resp.status)
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print(e.read().decode())
except Exception as e:
    print("Error:", e)
