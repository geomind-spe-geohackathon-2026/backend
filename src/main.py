import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    service = parser.add_mutually_exclusive_group(required=True)
    service.add_argument("--fastapi", action="store_true")
    service.add_argument("--celery", action="store_true")
    args = parser.parse_args()

    if args.fastapi:
        from src.fastapi import run
    else:
        from src.celery import run
    run()


if __name__ == "__main__":
    main()
