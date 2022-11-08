from setuptools import setup, find_packages

with open("requirements.txt", "r") as fs:
    reqs = [r for r in fs.read().splitlines() if (len(r) > 0 and not r.startswith("#"))]

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="napalm-sros",
    version="1.0.1",
    packages=find_packages(),
    author="Nokia",
    author_email="",
    description="Network Automation and Programmability Abstraction Layer with Multivendor support",
    classifiers=[
        "Topic :: Internet",
        "Programming Language :: Python :: 3.6",
        "Natural Language :: English",
        "Development Status :: 4 - Beta",
    ],
    url="https://github.com/napalm-automation/napalm-sros",
    include_package_data=True,
    install_requires=reqs,
    python_requires=">=3.6",
    long_description=long_description,
    long_description_content_type="text/markdown",
)
