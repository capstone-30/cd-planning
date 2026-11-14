import argparse
import ipaddress
import socket

import uvicorn

from .app import create_app
from .pipeline import DEFAULTS


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tailscale 또는 신뢰하는 LAN에서만 실행하세요. 포트 포워딩 금지.')
    parser.add_argument('--host', default='127.0.0.1', help='실기기는 PC의 Tailscale IP(100.x) 또는 사설 LAN IP 사용')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--data')
    parser.add_argument('--initial-frames', type=int, choices=range(30, 81), default=DEFAULTS['initial_frames'])
    parser.add_argument('--supplement-frames', type=int, choices=range(10, 41), default=DEFAULTS['supplement_frames'])
    parser.add_argument('--long-edge', type=int, choices=(960, 1280), default=960)
    parser.add_argument('--blur-threshold', type=float, default=0)
    parser.add_argument('--matcher', choices=('sequential', 'exhaustive'), default='sequential')
    args = parser.parse_args()
    address = ipaddress.ip_address(socket.gethostbyname(args.host))
    # Tailscale tailnet addresses (100.64.0.0/10) are reachable only by your own signed-in devices.
    tailnet = address.version == 4 and address in ipaddress.ip_network('100.64.0.0/10')
    if not (address.is_private or tailnet) or args.host == '0.0.0.0':
        parser.error('localhost, 신뢰하는 LAN의 사설 IP 또는 Tailscale IP(100.x)를 지정하세요.')
    if args.blur_threshold < 0 or not __import__('math').isfinite(args.blur_threshold):
        parser.error('선명도 임계값은 0 이상의 유한수여야 합니다.')
    config = {key: getattr(args, key) for key in ('initial_frames', 'supplement_frames', 'long_edge', 'blur_threshold', 'matcher')}
    print(f'접속 주소: http://{args.host}:{args.port} (토큰은 POC_TOKEN 환경 변수)')
    uvicorn.run(create_app(args.data, config=config), host=args.host, port=args.port, workers=1,
                timeout_graceful_shutdown=780)
