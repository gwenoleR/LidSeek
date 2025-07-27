from setuptools import setup, find_packages

setup(
    name="music-searcher",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'flask',
        'redis',
        'musicbrainzngs',
        'python-dotenv',
        'slskd-api',
        'music-tag',
    ],
    python_requires='>=3.11',
)