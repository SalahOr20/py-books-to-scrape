import os
import uuid
import requests
import csv
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed

base_url = "https://books.toscrape.com/"
images_dir = "images"
os.makedirs(images_dir, exist_ok=True)
csvs_dir = "csvs"
os.makedirs(csvs_dir, exist_ok=True)



def get_categories():
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return [(a.text.strip(), base_url + a['href']) for a in soup.select('.side_categories ul li ul li a')]

def scrape_book_details(book, category_name):
    title = book.find('h3').find('a')['title']
    relative_url = book.find('h3').find('a')['href']
    product_url = base_url + 'catalogue/' + relative_url.replace('../', '')

    response = requests.get(product_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    product_table = soup.find('table', class_='table table-striped')
    if product_table:
        product_info = product_table.find_all('tr')
        product_info_dict = {row.find('th').text: row.find('td').text for row in product_info}
    else:
        product_info_dict = {}

    price_including_tax = product_info_dict.get('Price (incl. tax)', 'N/A')
    price_excluding_tax = product_info_dict.get('Price (excl. tax)', 'N/A')
    number_available = product_info_dict.get('Availability', 'N/A').split(' ')[2] if 'Availability' in product_info_dict else 'N/A'
    upc = product_info_dict.get('UPC', 'N/A')
    review_rating = ' '.join(book.find('p', class_='star-rating').get('class')[1:])
    product_description_tag = soup.find('div', id='product_description')
    product_description = product_description_tag.find_next_sibling('p').text if product_description_tag else 'N/A'
    image_url = soup.find('div', class_='item active').find('img')['src'].replace('../../', base_url)
    image_filename = download_image(image_url, category_name)

    return (category_name, title, upc, price_including_tax, price_excluding_tax, number_available, review_rating, product_description, image_url, image_filename)

def download_image(image_url, category):
    try:
        random_string = str(uuid.uuid4())
        filename = f"{category}_{random_string}.jpg"
        filepath = os.path.join(images_dir, filename)
        if not image_url.startswith('http'):
            image_url = base_url + image_url.replace('../', '/')

        response = requests.get(image_url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return filename
        return None
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None




def scrape_books(category_name, category_url):
    books_data = []
    while category_url:
        response = requests.get(category_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        books = soup.select('article.product_pod')

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_book = {executor.submit(scrape_book_details, book, category_name): book for book in books}
            for future in as_completed(future_to_book):
                book_data = future.result()
                if book_data:
                    books_data.append(book_data)

        next_button = soup.select_one('li.next a')
        if next_button:
            next_page_url = next_button['href']
            category_url = '/'.join(category_url.split('/')[:-1]) + '/' + next_page_url
        else:
            break
    return books_data


def save_to_category_csv(data, category_name):
    filename = os.path.join(csvs_dir, f'{category_name}.csv')
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(
            ['Category', 'Title', 'UPC', 'Price Including Tax', 'Price Excluding Tax', 'Number Available', 'Rating',
             'Product Description', 'Image URL', 'Image Filename'])
        writer.writerows(data)


def calculate_category_stats():
    category_stats = {}
    output_filename = 'books_details_by_category_summary.csv'
    with open(output_filename, 'w', newline='', encoding='utf-8') as output_csv:
        fieldnames = ['Category', 'Number of Books', 'Average Price']
        writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
        writer.writeheader()
        for filename in os.listdir(csvs_dir):
            if filename.endswith(".csv") and filename != output_filename:
                category = os.path.splitext(filename)[0]
                filepath = os.path.join(csvs_dir, filename)

                num_books = 0
                total_price = 0.0

                with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        num_books += 1
                        price_text = row['Price Excluding Tax'].replace('£', '').replace('Â', '').strip()
                        total_price += float(price_text)

                average_price = total_price / num_books if num_books else 0
                category_stats[category] = {'num_books': num_books, 'average_price': average_price}
                writer.writerow({'Category': category, 'Number of Books': num_books, 'Average Price': f"£{average_price:.2f}"})

    return category_stats


def plot_books_per_category_pie_chart(category_stats):
    categories = [category for category in category_stats]
    num_books = [stats['num_books'] for stats in category_stats.values()]
    plt.figure(figsize=(8, 8))
    plt.pie(num_books, labels=categories, autopct='%1.1f%%', startangle=140)
    plt.title('Books Per Category')
    plt.axis('equal')
    plt.show()


def plot_average_price_histogram(category_stats):
    categories = [category for category in category_stats]
    average_prices = [stats['average_price'] for stats in category_stats.values()]
    plt.figure(figsize=(10, 6))
    plt.bar(categories, average_prices, color='skyblue')
    plt.xlabel('Category')
    plt.ylabel('Average Price (£)')
    plt.title('Average Price of Books Per Category')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()


def scrape():
    category_links = get_categories()
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_category = {executor.submit(scrape_books, category_name, category_url): (category_name, category_url)
                              for category_name, category_url in category_links}
        for future in as_completed(future_to_category):
            category_name, _ = future_to_category[future]
            books_data = future.result()
            save_to_category_csv(books_data, category_name)
    stats = calculate_category_stats()
    plot_books_per_category_pie_chart(stats)
    plot_average_price_histogram(stats)



scrape()
