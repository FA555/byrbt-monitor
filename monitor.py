# -*- coding: utf-8 -*-


import config
import logging
import os
import qbittorrentapi
import requests
import urllib.parse

from bs4 import BeautifulSoup
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import sleep
from typing import Iterable, Tuple


@dataclass(eq=True, frozen=True)
class Torrent:
    name: str
    id: int

    def get_link(self):
        return f'{config.BYRBT_BASE_URL}/download.php?id={self.id}&passkey={config.PASSKEY}'

    def __repr__(self):
        return f'[Torrent {self.id}: {self.name}]'


def setup():
    program_data_dir = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
    log_dir = Path(program_data_dir) / 'byrbt_monitor'
    os.makedirs(log_dir, exist_ok=True)
    log_file = log_dir / 'monitor.log'

    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8')
    console_handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%m-%d %H:%M:%S',
        handlers=[file_handler, console_handler],
    )


def send_notification(title: str, content_lines: list[str]):
    try:
        title_safe = urllib.parse.quote(title)
        body_safe = urllib.parse.quote(chr(10).join(content_lines))
        response = requests.get(f'{config.BARK_SELF_URL}/{title_safe}/{body_safe}', timeout=5)
        response.raise_for_status()
        logging.info('向 Bark 发送通知成功')
    except Exception as e:
        logging.error(f'向 Bark 发送通知时出错：{e}')


def push_to_qbittorrent(torrents: Iterable[Torrent]) -> bool:
    try:
        qbt_client = qbittorrentapi.Client(config.QBT_URL)
        qbt_client.auth_log_in()

        download_links = [torrent.get_link() for torrent in torrents]
        qbt_client.torrents_add(urls=download_links, save_path=config.DOWNLOAD_DIR)

        logging.info(f'推送 {len(torrents)} 个种子到 qBittorrent 成功')
        return True
    except Exception as e:
        logging.error(f'推送种子到 qBittorrent 时出错：{e}')
        return False


def fake_push():
    torrents = [
        Torrent(name='[演讲交流][习近平总书记率新任常委与记者见面会][WMV][2012-11-15]', id=107466),
    ]
    try:
        qbt_client = qbittorrentapi.Client(config.QBT_URL)
        qbt_client.auth_log_in()

        download_links = [torrent.get_link() for torrent in torrents]
        qbt_client.torrents_add(urls=download_links, save_path=config.DOWNLOAD_DIR)

        logging.info(f'推送 {len(torrents)} 个种子到 qBittorrent 成功')
        return True
    except Exception as e:
        logging.error(f'推送种子到 qBittorrent 时出错：{e}')
        return False


def extract_torrent(row: BeautifulSoup) -> Torrent | None:
    title_tag = row.find('a', href=lambda h: h and 'details.php?id=' in h)
    download_tag = row.find('a', href=lambda h: h and 'download.php?id=' in h)
    if not title_tag or not download_tag:
        logging.warning(f'解析种子信息失败：{title_tag = }, {download_tag = }')
        return None

    return Torrent(
        name=title_tag.get('title') or title_tag.text.strip(),
        id=int(download_tag['href'].split('id=')[1]),
    )


def get_bidding_torrents():
    try:
        response = requests.get(f'{config.BYRBT_BASE_URL}/torrents.php', **config.GET_ARGS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        torrent_table = soup.find('table', class_='torrents')
        if not torrent_table:
            logging.critical('获取种子列表失败，可能登录状态异常')
            logging.info(f'{response.text = }')
            send_notification(title='获取种子列表失败', content_lines=['可能登录状态异常，请检查日志'])
            exit(1)

        current_bidding_torrents = {
            extract_torrent(row)
            for row in torrent_table.find_all('tr')[1:]
            if row.find('div', class_=lambda c: c and 'sticky-buy' in c)
        } - {None}

        return current_bidding_torrents

    except Exception as e:
        logging.error(f'获取种子列表失败：{e}')


def parse_push_results(status: bool, torrents: set[Torrent]) -> Tuple[str, list[str]]:
    count = len(torrents)

    title = f'新增种子{"成功" if status else "失败"}'
    content_lines = [f'共{count}个种子']
    return title, content_lines


if __name__ == '__main__':
    setup()

    bidding_torrents = set()
    while True:
        if (new_bidding_torrents := get_bidding_torrents()) is not None:
            logging.debug(f'获取到 {len(new_bidding_torrents)} 个竞价置顶种子')

            if delta := new_bidding_torrents - bidding_torrents:
                for torrent in delta:
                    logging.info(f'新竞价置顶种子：{torrent = }')
                send_notification(*parse_push_results(push_to_qbittorrent(delta), delta))

            bidding_torrents = new_bidding_torrents

        sleep(20)
