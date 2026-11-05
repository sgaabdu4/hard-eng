import importlib

if __name__ == "__main__":
    raise SystemExit(importlib.import_module("trello_board.commands").main())
