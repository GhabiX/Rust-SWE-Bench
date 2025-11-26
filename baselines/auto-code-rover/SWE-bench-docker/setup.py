from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="swe_bench_docker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
    include_package_data=True,
    description="A Docker based solution of the SWE-bench evaluation framework",
    author="Albert Örwall",
    author_email="albert@a20g.se",
    url="https://github.com/aorwall/SWE-bench-docker",
)
