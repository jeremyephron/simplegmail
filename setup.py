import setuptools

setuptools.setup(
    name="simplegmail",
    version="4.0.1",
    url="https://github.com/jeremyephron/simplegmail",
    author="Jeremy Ephron",
    author_email="jeremyephron@gmail.com",
    description="A simple Python API client for Gmail.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    install_requires=[
        'google-api-python-client>=1.7.3',
        'bs4>=0.0.1',
        'python-dateutil>=2.8.1',
        'oauth2client>=4.1.3',
        'lxml>=4.4.2'
    ],
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
