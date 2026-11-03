import sys
from .guides import make_report

if __name__ == '__main__':
    make_report(sys.argv[1], int(sys.argv[2]), sys.argv[3])
