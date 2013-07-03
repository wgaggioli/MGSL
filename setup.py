from setuptools import setup, find_packages


setup(
    author="Will Gaggioli",
    author_email="wgaggioli@gmail.com",
    name='pynecroud',
    version="0.1",
    description='Utility for Managing Minecraft Worlds on EC2 instances',
    url='',
    license='MIT License',
    platforms=['OS Independent'],
    install_requires=[
        'boto',
    ],
    packages=find_packages(exclude=[])
)
