from setuptools import setup, find_packages

setup(
    name="ai-commit",
    version="0.2.0",
    packages=find_packages(),
    install_requires=[
        "setuptools>=58.0.0",
        "openai>=1.0.0",
        "python-dotenv>=0.19.0",
    ],
    entry_points={
        'console_scripts': [
            'ai-commit=ai_commit.cli:main',
        ],
    },
    author="zero0043",
    description="AI-powered git commit message generator",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/zero0043/py-ai-commit",
    python_requires=">=3.8",
)
