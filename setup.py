from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="photocull",
    version="0.1.0",
    author="PhotoCull",
    description="Intelligent photo selection tool using perceptual hashing and computer vision",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.8.0",
        "mediapipe>=0.10.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "imagehash>=4.3.0",
        "python-dateutil>=2.8.0",
        "ExifRead>=3.0.0",
    ],
    extras_require={
        "embeddings": [
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "open-clip-torch>=2.20.0",
            "faiss-cpu>=1.7.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "photocull=photocull.main:main",
        ],
    },
)