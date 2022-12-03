from bs4 import BeautifulSoup
import requests
import praw
import configparser
import sqlite3
from sqlite3 import Error
import argparse
import os
import schedule
import time


def db_connect():
    try:
        conn = sqlite3.connect('data.db')
        return conn
    except Error as e:
        print(e)


def get_random_comic(conn):
    cur = conn.cursor()
    cur.execute("SELECT ID, url, comic_date, downloaded FROM comics WHERE posted = 0 ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    return row


def create_table(conn):
    create_table = """CREATE TABLE IF NOT EXISTS comics (
                                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                                        url TEXT NOT NULL UNIQUE,
                                        comic_date TEXT NOT NULL,
                                        posted INTEGER DEFAULT 0,
                                        downloaded INTEGER DEFAULT 0
                                        );"""
    conn.execute(create_table)


def insert_row(conn, url, comic_date, downloaded):
    conn.execute(
        "INSERT OR IGNORE INTO comics (url, comic_date, downloaded) VALUES (?, ?, ?);", (url, comic_date, downloaded))
    conn.commit()


def update_row(conn, id):
    conn.execute("UPDATE comics SET posted = 1 WHERE ID = ?;", (id,))
    conn.commit()


def reset_posted(conn):
    conn.execute("UPDATE comics SET posted = 0;")
    conn.commit()


def lovely_soup(url):
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1'})
    return BeautifulSoup(r.content, 'lxml')


def get_comics(conn, download):
    soup = lovely_soup('https://www.gocomics.com/calvinandhobbes')
    nav_links = soup.select_one('ul.js-tab-nav').select('a.nav-link')
    for nav_link in nav_links:
        if nav_link.text == 'Comics':
            comic_url = nav_link['href']

    while True:
        if 'http' in comic_url:
            comic_url = comic_url
        else:
            comic_url = f'https://www.gocomics.com{comic_url}'
        soup = lovely_soup(comic_url)
        if not soup.select_one('a.js-previous-comic.disabled'):
            img_url = soup.find('meta', attrs={'property': 'og:image', 'content': True})['content']
            img_url = f'{img_url}.jpg'
            comic_url = soup.select_one('a.js-previous-comic')['href']
            comic_url = f'https://www.gocomics.com{comic_url}'
            comic_date = '-'.join(comic_url.split('/')[4:])
            downloaded = 0

            if download:
                download_image(img_url, comic_date)
                downloaded = 1

            insert_row(conn, img_url, comic_date, downloaded)
            print(comic_date)
        else:
            return


def download_image(img_url, file_name):
    img = requests.get(img_url).content
    image_path = f'images/{file_name}.jpg'
    with open(image_path, 'wb') as f:
        f.write(img)
    return image_path


def reddit_poster(conn, reddit, target_subreddit):
    row = get_random_comic(conn)

    if row:
        comic_id, comic_url, comic_date, downloaded = row[0], row[1], row[2], row[3]
        print(f'Posting comic {comic_date}')

        image_path = f'/images/{comic_date}.jpg'
        if not downloaded:
            image_path = download_image(comic_url, comic_date)
            os.remove(image_path)

        reddit.subreddit(target_subreddit).submit_image(comic_date, image_path)
        update_row(conn, comic_id)
    else:
        reset_posted(conn)
        reddit_poster(conn, reddit, target_subreddit)


def main():
    config = configparser.ConfigParser()
    config.read('conf.ini')
    target_subreddit = config['REDDIT']['reddit_target_subreddit']
    schedule_time = config['SETTINGS']['schedule_time']

    conn = db_connect()
    create_table(conn)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s', '--scrape_images',
        help="Scrape comics without downloading images",
        action="store_true"
    )

    parser.add_argument(
        '-d', '--download_images',
        help="Scrape comics and download images",
        action="store_true"
    )

    args = parser.parse_args()

    scrape, download = False, False

    if args.scrape_images:
        print('Scrape comics without download')
        scrape = True
    if args.download_images:
        print('Scrape comics and download')
        scrape = True
        download = True

    if scrape:
        get_comics(conn, download)
    else:
        reddit = praw.Reddit(
            username=config['REDDIT']['reddit_user'],
            password=config['REDDIT']['reddit_pass'],
            client_id=config['REDDIT']['reddit_client_id'],
            client_secret=config['REDDIT']['reddit_client_secret'],
            user_agent='Reddit Go Comics (by u/impshum)'
        )

        reddit.validate_on_submit = True

        reddit_poster(conn, reddit, target_subreddit)
        schedule.every().day.at(schedule_time).do(reddit_poster, conn, reddit, target_subreddit)

        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == '__main__':
    main()
