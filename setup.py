import setuptools

setuptools.setup(
    name="simplegmail",
    version="4.1.1",
    url="https://github.com/jeremyephron/simplegmail",
    author="Jeremy Ephron",
    author_email="jeremye@cs.stanford.edu",
    description="A simple Python API client for Gmail.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
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
        'Programming Language :: Python :: 3.6',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
