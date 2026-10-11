from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="spectrumalyzer",
    version="0.1.0",
    author="Dream-Pixels-Forge",
    author_email="dev@dream-pixels-forge.example.com",
    description="Audio beat analysis tool for motion graphics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Dream-Pixels-Forge/spectrumalyzer",
    py_modules=["spectrumalyzer"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        # Add your dependencies here
        # For example: "numpy>=1.19.0", "scipy>=1.5.0"
    ],
)
