"""Builds the two Cython competitors in-place (needs gcc + Cython).

Run from this directory:  python setup_cython.py
"""
from setuptools import setup
from Cython.Build import cythonize

setup(
    name="sieve_cy_competitors",
    ext_modules=cythonize(
        ["kernel_cy.pyx", "kernel_cy_fast.pyx"],
        quiet=True,
        compiler_directives={"language_level": "3"},
    ),
    script_args=["build_ext", "--inplace", "-q"],
)
