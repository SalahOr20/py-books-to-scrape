import os
import shutil
import uuid
import requests
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

browser = webdriver.Firefox()

def get_links():
    j = 1
    n = 0
    url = f'https://books.toscrape.com/catalogue/page-{j}.html'
    browser.get(url)
    links = []
    categories = []

    for c in range(1, 51):
        category = browser.find_element(by=By.XPATH,
                                        value=f'//*[@id="default"]/div/div/div/aside/div[2]/ul/li/ul/li[{c}]').text
        categories.append(category)
        print(category)

    while n <= 1000 and j <= 50:
        n += 1
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        link = browser.find_element(by=By.XPATH,
                                    value=f'//*[@id="default"]/div/div/div/div/section/div[2]/ol/li[{n}]/article/div[1]/a').get_attribute(
            'href')
        links.append(link)

        if n % 20 == 0:
            j += 1
            n = 1
            browser.get(f'https://books.toscrape.com/catalogue/page-{j}.html')

    return links, categories

def download_image(url, category):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            image_name = f'images/{category}_{uuid.uuid4()}.png'
            with open(image_name, 'wb') as image_file:
                response.raw.decode_content = True
                shutil.copyfileobj(response.raw, image_file)
            return image_name
        else:
            print(f"Failed to download image for category {category}: HTTP status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading image for category {category}: {e}")
        return None

def download_images_parallel(urls_categories):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_image, url, category) for url, category in urls_categories]
        for future in futures:
            future.result()

def get_books(links):
    books = {}
    n = 0
    urls_categories = []
    for link in links:
        browser.get(link)
        try:
            category = browser.find_element(by=By.XPATH, value='//*[@id="default"]/div/div/ul/li[3]/a').text
        except Exception as e:
            category = ""
            print(f"Error retrieving category for link {link}: {e}")
            continue

        img_url = browser.find_element(by=By.XPATH, value='//*[@id="product_gallery"]/div/div/div/img').get_attribute(
            'src')
        urls_categories.append((img_url, category))

        try:
            title = browser.find_element(by=By.XPATH, value='//*[@id="content_inner"]/article/div[1]/div[2]/h1').text
        except Exception as e:
            title = ""
            print(f"Error retrieving title for link {link}: {e}")
            continue

        try:
            upc = browser.find_element(by=By.XPATH, value='//*[@id="content_inner"]/article/table/tbody/tr[1]/td').text
        except Exception as e:
            upc = ""
            print(f"Error retrieving UPC for link {link}: {e}")
            continue

        try:
            price_including_taxe_text = browser.find_element(by=By.XPATH,
                                                             value='//*[@id="content_inner"]/article/table/tbody/tr[4]/td').text
            price_including_taxe_text = price_including_taxe_text.replace('£', '').strip()
            price_including_taxe = float(price_including_taxe_text)
        except Exception as e:
            price_including_taxe = 0.0
            print(f"Error retrieving price including tax for link {link}: {e}")
            continue

        try:
            price_excluding_taxe_text = browser.find_element(by=By.XPATH,
                                                             value='//*[@id="content_inner"]/article/table/tbody/tr[4]/td').text
            price_excluding_taxe_text = price_excluding_taxe_text.replace('£', '').strip()
            price_excluding_taxe = float(price_excluding_taxe_text)
        except Exception as e:
            price_excluding_taxe = 0.0
            print(f"Error retrieving price excluding tax for link {link}: {e}")
            continue

        number_pattern = re.compile(r'\d+')
        try:
            number_available_text = browser.find_element(by=By.XPATH,
                                                         value='//*[@id="content_inner"]/article/table/tbody/tr[6]/td').text
            numbers = number_pattern.findall(number_available_text)
            number_available = int(''.join(numbers))
        except Exception as e:
            number_available = ""
            print(f"Error retrieving number available for link {link}: {e}")
            continue

        try:
            review_rating = browser.find_element(by=By.XPATH,
                                                 value='//*[@id="content_inner"]/article/table/tbody/tr[7]/td').text
        except Exception as e:
            review_rating = ""
            print(f"Error retrieving review rating for link {link}: {e}")
            continue

        try:
            description = browser.find_element(by=By.XPATH, value='//*[@id="content_inner"]/article/p').text
        except Exception as e:
            description = ""
            print(f"Error retrieving description for link {link}: {e}")
            continue

        book = {
            'category': category,
            'title': title,
            'universal_product_code [upc]': upc,
            'price_including_tax': price_including_taxe,
            'price_excluding_tax': price_excluding_taxe,
            'number_available': number_available,
            'review_rating': int(review_rating),
            'product_description': description,
            'image_url': img_url
        }
        print(book)
        books[n] = book
        n += 1

    download_images_parallel(urls_categories)
    return books

def match_books_to_categories(books, categories):
    categorized_books = {category: [] for category in categories}

    for book in books.values():
        category = book['category']
        categorized_books[category].append(book)

    for category, books_in_category in categorized_books.items():
        if books_in_category:  # Vérifie si la liste n'est pas vide
            filename = f'{category}.csv'
            filepath = os.path.join('csvs', filename)
            with open(filepath, 'w', newline='', encoding='utf-8') as category_file:
                writer = csv.DictWriter(category_file, fieldnames=books_in_category[0].keys())
                writer.writeheader()
                writer.writerows(books_in_category)
        else:
            print(f"No books found for category: {category}")

    return categorized_books

def calculate_category_stats():
    category_stats = {}

    with open('books_details_by_category.csv', 'w', newline='', encoding='utf-8') as output_csv:
        fieldnames = ['Category', 'Number of Books', 'Average Price']
        writer = csv.DictWriter(output_csv, fieldnames=fieldnames)
        writer.writeheader()

        for filename in os.listdir('csvs'):
            if filename.endswith(".csv"):
                category = os.path.splitext(filename)[0]
                filepath = os.path.join('csvs', filename)

                num_books = 0
                total_price = 0.0

                with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        num_books += 1
                        total_price += float(row['price_excluding_tax'])

                if num_books > 0:
                    average_price = total_price / num_books
                else:
                    average_price = 0.0

                category_stats[category] = {'num_books': num_books, 'average_price': average_price}

                writer.writerow({'Category': category, 'Number of Books': num_books, 'Average Price': average_price})

    return category_stats

def plot_books_per_category_pie_chart(category_stats):
    categories = list(category_stats.keys())
    num_books = [category_stats[category]['num_books'] for category in categories]

    total_books = sum(num_books)
    percentages = [(num_book / total_books) * 100 for num_book in num_books]

    plt.figure(figsize=(8, 8))
    plt.pie(percentages, labels=categories, autopct='%1.1f%%', startangle=140)
    plt.title('Books Per Category')
    plt.axis('equal')
    plt.show()

def plot_average_price_histogram(category_stats):
    categories = list(category_stats.keys())
    average_prices = [category_stats[category]['average_price'] for category in categories]

    plt.figure(figsize=(10, 6))
    plt.bar(categories, average_prices, color='skyblue')
    plt.xlabel('Category')
    plt.ylabel('Average Price')
    plt.title('Average Price of Books Per Category')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

links, categories = get_links()
books = get_books(links)
match_books_to_categories(books, categories)
stats = calculate_category_stats()
plot_books_per_category_pie_chart(stats)
plot_average_price_histogram(stats)
