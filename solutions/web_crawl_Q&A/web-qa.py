################################################################################
# Step 1
################################################################################

import sys
import requests
import re
import urllib.request
from bs4 import BeautifulSoup
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urlparse
import os
import pandas as pd
import tiktoken
import openai
from openai.embeddings_utils import distances_from_embeddings
import pandas as pd
import numpy as np
from openai.embeddings_utils import distances_from_embeddings, cosine_similarity
import matplotlib.pyplot as plt

# Regex pattern to match a URL
HTTP_URL_PATTERN = r'^http[s]*://.+'


def build_embeddings_from_web(full_url, domain=None, clean=False):
    # # Define root domain to crawl
    # domain = "www.infrakraft.se"
    # full_url = "https://www.infrakraft.se/"

    # TODO: Extract domain from full_url
    if domain is None:
        domain = urlparse(full_url).netloc

    # Create a class to parse the HTML and get the hyperlinks

    class HyperlinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            # Create a list to store the hyperlinks
            self.hyperlinks = []

        # Override the HTMLParser's handle_starttag method to get the hyperlinks
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)

            # If the tag is an anchor tag and it has an href attribute, add the href attribute to the list of hyperlinks
            if tag == "a" and "href" in attrs:
                self.hyperlinks.append(attrs["href"])

    ################################################################################
    # Step 2
    ################################################################################

    # Function to get the hyperlinks from a URL

    def get_hyperlinks(url):

        # Try to open the URL and read the HTML
        try:
            # Open the URL and read the HTML
            with urllib.request.urlopen(url) as response:

                # If the response is not HTML, return an empty list
                if not response.info().get('Content-Type').startswith("text/html"):
                    return []

                # Decode the HTML
                result = response.read()
                try:
                    html = result.decode('utf-8')
                except UnicodeDecodeError:
                    html = result.decode('latin-1')
        except Exception as e:
            print(e)
            return []

        # Create the HTML Parser and then Parse the HTML to get hyperlinks
        parser = HyperlinkParser()
        parser.feed(html)

        return parser.hyperlinks

    ################################################################################
    # Step 3
    ################################################################################

    # Function to get the hyperlinks from a URL that are within the same domain

    def get_domain_hyperlinks(local_domain, url):
        clean_links = []
        for link in set(get_hyperlinks(url)):
            clean_link = None

            # If the link is a URL, check if it is within the same domain
            if re.search(HTTP_URL_PATTERN, link):
                # Parse the URL and check if the domain is the same
                url_obj = urlparse(link)
                if url_obj.netloc == local_domain:
                    clean_link = link

            # If the link is not a URL, check if it is a relative link
            else:
                if link.startswith("/"):
                    link = link[1:]
                elif link.startswith("#") or link.startswith("mailto:"):
                    continue
                clean_link = "https://" + local_domain + "/" + link

            if clean_link is not None:
                if clean_link.endswith("/"):
                    clean_link = clean_link[:-1]
                clean_links.append(clean_link)

        # Return the list of hyperlinks that are within the same domain
        return list(set(clean_links))

    ################################################################################
    # Step 4
    ################################################################################

    def crawl(url):
        # Parse the URL and get the domain
        local_domain = urlparse(url).netloc

        # Create a queue to store the URLs to crawl
        queue = deque([url])

        # Create a set to store the URLs that have already been seen (no duplicates)
        seen = set([url])

        # Create a directory to store the text files
        if not os.path.exists("text/"):
            os.mkdir("text/")

        if not os.path.exists("text/"+local_domain+"/"):
            os.mkdir("text/" + local_domain + "/")

        # Create a directory to store the csv files
        if not os.path.exists("processed/" + local_domain + "/"):
            os.mkdir("processed/" + local_domain + "/")

        print("Crawling domain: " + domain, local_domain)
        if clean:
            # remove all files in text/ and processed/
            for file in os.listdir("text/"+local_domain+"/"):
                os.remove("text/"+local_domain+"/" + file)
            for file in os.listdir("processed/"+local_domain+"/"):
                os.remove("processed/"+local_domain+"/" + file)
        else:
            return

        print("Crawling domain: " + domain)
        print("            url: " + full_url)

        # While the queue is not empty, continue crawling
        while queue:

            # Get the next URL from the queue
            url = queue.pop()
            print(url)  # for debugging and to see the progress

            try:
                filename = 'text/' + local_domain+'/' + \
                    url[8:].replace("/", "_") + ".txt"

                # If the text file already exists, skip it
                if os.path.exists(filename):
                    continue

                # Save text from the url to a <url>.txt file
                with open(filename, "w", encoding="utf-8") as f:

                    # Get the text from the URL using BeautifulSoup
                    soup = BeautifulSoup(requests.get(url).text, "html.parser")

                    # Get the text but remove the tags
                    text = soup.get_text()

                    # If the crawler gets to a page that requires JavaScript, it will stop the crawl
                    if ("You need to enable JavaScript to run this app." in text):
                        print("Unable to parse page " + url +
                              " due to JavaScript being required")

                    # Otherwise, write the text to the file in the text directory
                    f.write(text)
            except:
                print("Unable to parse page " + url)

            # Get the hyperlinks from the URL and add them to the queue
            for link in get_domain_hyperlinks(local_domain, url):
                if link not in seen:
                    queue.append(link)
                    seen.add(link)

    crawl(full_url)

    ################################################################################
    # Step 5
    ################################################################################

    def remove_newlines(serie):
        serie = serie.str.replace('\n', ' ')
        serie = serie.str.replace('\\n', ' ')
        serie = serie.str.replace('  ', ' ')
        serie = serie.str.replace('  ', ' ')
        return serie

    ################################################################################
    # Step 6
    ################################################################################
    def make_sure_folder_exists(filename):
        folder = os.path.dirname(filename)
        if not os.path.exists(folder):
            os.makedirs(folder)

    scraped_filename = "processed/" + domain + "/scraped.csv"
    make_sure_folder_exists(scraped_filename)

    if not os.path.exists(scraped_filename):
        # Create a list to store the text files
        texts = []

        # Get all the text files in the text directory
        for file in os.listdir("text/" + domain + "/"):

            # Open the file and read the text
            with open("text/" + domain + "/" + file, "r", encoding="utf-8") as f:
                text = f.read()

                # Omit the first 11 lines and the last 4 lines, then replace -, _, and #update with spaces.
                texts.append(
                    (file[len(domain)+1:-4].replace('-', ' ').replace('_', ' ').replace('#update', ''), text))

        # Create a dataframe from the list of texts
        df = pd.DataFrame(texts, columns=['fname', 'text'])

        # Set the text column to be the raw text with the newlines removed
        df['text'] = df.fname + ". " + remove_newlines(df.text)
        df.to_csv(scraped_filename)
        df.head()

    ################################################################################
    # Step 7
    ################################################################################

    embeddings_filename = "processed/" + domain + "/embeddings.csv"
    if not os.path.exists(embeddings_filename):
        # Load the cl100k_base tokenizer which is designed to work with the ada-002 model
        tokenizer = tiktoken.get_encoding("cl100k_base")

        df = pd.read_csv(scraped_filename, index_col=0)
        df.columns = ['title', 'text']

        # Tokenize the text and save the number of tokens to a new column
        df['n_tokens'] = df.text.apply(lambda x: len(tokenizer.encode(x)))

        # Visualize the distribution of the number of tokens per row using a histogram
        df.n_tokens.hist()

        ################################################################################
        # Step 8
        ################################################################################

        max_tokens = 500

        # Function to split the text into chunks of a maximum number of tokens

        def split_into_many(text, max_tokens=max_tokens):

            # Split the text into sentences
            sentences = text.split('. ')

            # Get the number of tokens for each sentence
            n_tokens = [len(tokenizer.encode(" " + sentence))
                        for sentence in sentences]

            chunks = []
            tokens_so_far = 0
            chunk = []

            # Loop through the sentences and tokens joined together in a tuple
            for sentence, token in zip(sentences, n_tokens):

                # If the number of tokens so far plus the number of tokens in the current sentence is greater
                # than the max number of tokens, then add the chunk to the list of chunks and reset
                # the chunk and tokens so far
                if tokens_so_far + token > max_tokens:
                    chunks.append(". ".join(chunk) + ".")
                    chunk = []
                    tokens_so_far = 0

                # If the number of tokens in the current sentence is greater than the max number of
                # tokens, go to the next sentence
                if token > max_tokens:
                    continue

                # Otherwise, add the sentence to the chunk and add the number of tokens to the total
                chunk.append(sentence)
                tokens_so_far += token + 1

            return chunks

        shortened = []

        # Loop through the dataframe
        for row in df.iterrows():

            # If the text is None, go to the next row
            if row[1]['text'] is None:
                continue

            # If the number of tokens is greater than the max number of tokens, split the text into chunks
            if row[1]['n_tokens'] > max_tokens:
                shortened += split_into_many(row[1]['text'])

            # Otherwise, add the text to the list of shortened texts
            else:
                shortened.append(row[1]['text'])

        ################################################################################
        # Step 9
        ################################################################################

        df = pd.DataFrame(shortened, columns=['text'])
        df['n_tokens'] = df.text.apply(lambda x: len(tokenizer.encode(x)))
        df.n_tokens.hist()
        # Save the histogram to a file
        plt.savefig('processed/' + domain + '/n_tokens.png')

        ################################################################################
        # Step 10
        ################################################################################

        df['embeddings'] = df.text.apply(lambda x: openai.Embedding.create(
            input=x, engine='text-embedding-ada-002')['data'][0]['embedding'])
        df.to_csv(embeddings_filename)
        df.head()

    ################################################################################
    # Step 11
    ################################################################################

    df = pd.read_csv(embeddings_filename, index_col=0)
    df['embeddings'] = df['embeddings'].apply(eval).apply(np.array)

    df.head()

    return df

    ################################################################################
    # Step 12
    ################################################################################


def create_context(
    question, df, max_len=1800, size="ada"
):
    """
    Create a context for a question by finding the most similar context from the dataframe
    """

    # Get the embeddings for the question
    q_embeddings = openai.Embedding.create(
        input=question, engine='text-embedding-ada-002')['data'][0]['embedding']

    # Get the distances from the embeddings
    df['distances'] = distances_from_embeddings(
        q_embeddings, df['embeddings'].values, distance_metric='cosine')

    returns = []
    cur_len = 0

    # Sort by distance and add the text to the context until the context is too long
    for i, row in df.sort_values('distances', ascending=True).iterrows():

        # Add the length of the text to the current length
        cur_len += row['n_tokens'] + 4

        # If the context is too long, break
        if cur_len > max_len:
            break

        # Else add it to the text that is being returned
        returns.append(row["text"])

    # Return the context
    return "\n\n###\n\n".join(returns)


def answer_question(
    df,
    model="text-davinci-003",
    question="Am I allowed to publish model outputs to Twitter, without a human review?",
    max_len=1800,
    size="ada",
    debug=False,
    max_tokens=250,
    stop_sequence=None
):
    """
    Answer a question based on the most similar context from the dataframe texts
    """
    context = create_context(
        question,
        df,
        max_len=max_len,
        size=size,
    )
    # If debug, print the raw model response
    if debug:
        print("Context:\n" + context)
        print("\n\n")

    try:
        # Create a completions using the questin and context
        response = openai.Completion.create(
            prompt=f"Answer the question based on the context below, and if the question can't be answered based on the context, say \"I don't know\"\n\nContext: {context}\n\n---\n\nQuestion: {question}\nAnswer:",
            temperature=0,
            max_tokens=max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=stop_sequence,
            model=model,
        )
        return response["choices"][0]["text"].strip()
    except Exception as e:
        print(e)
        return ""

################################################################################
# Step 13
################################################################################


# df = build_embeddings_from_web("https://izaxon.se/", clean=True)

# # print(answer_question(df, question="What does Infrakraft do?", debug=False))
# # print(answer_question(df, question="How old is Infrakraft?"))

# print(answer_question(df, question="What does Izaxon do?", debug=False))
# print(answer_question(df, question="What is the VAT?", debug=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 web-qa.py <url> [question]")
        exit(1)
    url = sys.argv[1]
    # append / if not present
    if url[-1] != "/":
        url += "/"
    question = sys.argv[2] if len(sys.argv) > 2 else None
    print("\nRunning with url:", url, "\n    and question:", question, "\n\n")
    df = build_embeddings_from_web(url, clean=question is None)
    if question is not None:
        print(answer_question(df, question=question, debug=False))
    else:
        print(df.head())
