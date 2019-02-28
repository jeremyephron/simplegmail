import setuptools

setuptools.setup(
    name="simplegmail",
    version="0.0.4",
    url="https://github.com/illiteratecoder/simple-gmail",
    author="Jeremy Ephron",
    author_email="jeremyephron@gmail.com",
    description="A simple Python API client for Gmail.",
    long_description=open('README.md').read(),
    packages=setuptools.find_packages(),
    install_requires=[
        'google-api-python-client>=1.7.3',
        'bs4>=0.0.1',
        'py-dateutil>=2.2',
        'oauth2client>=4.1.3'
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
    classifiers=(
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)