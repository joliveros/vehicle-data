#!/usr/bin/env python

import alog
import dataclasses
import argparse
import click
from scraper.marketplace_cars import Cars


@click.command()
@click.option("--headless", "-H", is_flag=True)
@click.option("--dry-run", "-d", is_flag=True)
# @click.option("--window-size", "-w", default="3m", type=str)
def main(**kwargs):
    field_names = set(f.name for f in dataclasses.fields(Cars))
    Cars(**{k: v for k, v in kwargs.items() if k in field_names})

if __name__ == "__main__":
    main()
