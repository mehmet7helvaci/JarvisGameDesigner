from setuptools import setup, find_packages

setup(
    name="jarvis-game-designer",
    version="0.1.0",
    packages=find_packages(include=["game_designer*", "seeds*"], exclude=["tests*"]),
    include_package_data=True,
    python_requires=">=3.10",
)
