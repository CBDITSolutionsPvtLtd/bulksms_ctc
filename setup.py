from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [line.strip() for line in f if line.strip()]

setup(
    name="bulksms_ctc",
    version="1.0.0",
    description="BulkSMS IVR Click-to-Call Integration for ERPNext",
    author="GetmyERP",
    author_email="manoj@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)