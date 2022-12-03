import praw
import configparser
import os
import requests
import schedule
from bs4 import BeautifulSoup
import requests
import time


def lovely_soup(url):
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1'})
    return r.url, BeautifulSoup(r.content, 'lxml')


def get_random_comic(target_comic):
    url, soup = lovely_soup(f'https://www.gocomics.com/random/{target_comic}')
    comic_url = soup.find('meta', attrs={'property': 'og:image', 'content': True})['content'] + '.jpg'
    comic_date = '-'.join(url.split('/')[4:])
    return comic_url, comic_date


def download_image(comic_url, file_name):
    img = requests.get(comic_url).content
    image_path = f'images/{file_name}.jpg'
    with open(image_path, 'wb') as f:
        f.write(img)
    return image_path


def reddit_poster(target_comic, reddit, target_subreddit, title_prefix):
    comic_url, comic_date = get_random_comic(target_comic)
    image_path = download_image(comic_url, comic_date)
    title = f'{title_prefix} - {comic_date}'
    reddit.subreddit(target_subreddit).submit_image(title, image_path)
    os.remove(image_path)
    print(f'Posted {title}')


def main():
    config = configparser.ConfigParser()
    config.read('conf.ini')
    target_subreddit = config['REDDIT']['reddit_target_subreddit']
    schedule_time = config['SETTINGS']['schedule_time']
    target_comic = config['SETTINGS']['target_comic']
    title_prefix = config['SETTINGS']['title_prefix']

    reddit = praw.Reddit(
        username=config['REDDIT']['reddit_user'],
        password=config['REDDIT']['reddit_pass'],
        client_id=config['REDDIT']['reddit_client_id'],
        client_secret=config['REDDIT']['reddit_client_secret'],
        user_agent='Reddit Daily Go Comics Poster (by u/impshum)'
    )

    reddit.validate_on_submit = True

    reddit_poster(target_comic, reddit, target_subreddit, title_prefix)
    schedule.every().day.at(schedule_time).do(reddit_poster, target_comic, reddit, target_subreddit, title_prefix)
    # https://schedule.readthedocs.io/

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    main()
