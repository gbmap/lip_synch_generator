from setuptools import setup, find_packages

setup(
    name="lip_synch_generator",
    version="0.1.0",
    packages=find_packages(include=["lip_synch_generator"]),
    package_data={"lip_synch_generator": ["*.yml"]},
    include_package_data=True,
    install_requires=[
        "allosaurus",
        "moviepy",
        "pyyaml",
        "Pillow"
    ],
    entry_points={
        "console_scripts": [
            "lsg = lip_synch_generator.lsg:main"
        ]
    },
)
