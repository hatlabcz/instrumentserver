from instrumentserver.client import QtClient


if __name__ == "__main__":
    cli = QtClient()
    dac = cli.get_instrument("dac")


