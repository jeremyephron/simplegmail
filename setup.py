from pathlib import Path

import setuptools

README = Path(__file__).with_name('README.md').read_text(encoding='utf-8')

setuptools.setup(
    name="simplegmail",
    version="5.0.0",
    url="https://github.com/jeremyephron/simplegmail",
    author="Jeremy Ephron",
    author_email="jeremye@cs.stanford.edu",
    description="A simple Python API client for Gmail.",
    license="MIT",
    long_description=README,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    python_requires='>=3.10',
    install_requires=[
        'google-api-python-client>=1.7.3',
        'google-auth>=2.15.0',
        'google-auth-oauthlib>=1.0.0',
        'beautifulsoup4>=4.12.1',
        'python-dateutil>=2.8.1',
        'lxml>=4.4.2'
    ],
    extras_require={
        'test': ['pytest'],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        "Operating System :: OS Independent",
    ],
)
