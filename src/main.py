"""
Entry point for Project Athena.
"""

from bootstrap import create_athena


def main():
    athena = create_athena()
    athena.run()


if __name__ == "__main__":
    main()