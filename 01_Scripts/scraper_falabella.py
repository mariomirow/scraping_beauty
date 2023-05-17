#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!pip install nest-asyncio


# In[ ]:


import numpy as np
import pandas as pd
from requests_html import HTMLSession#, AsyncHTMLSession
from bs4 import BeautifulSoup
from datetime import date
import re
import json
from urllib.parse import unquote


# In[ ]:


debug_mode = False


# In[ ]:


#import nest_asyncio
#nest_asyncio.apply()

#r = await asession.get(links[0])
#await r.html.arender(scrolldown=True)


# # Mapeando a árvore de URLs

# In[ ]:


def filter_links(links, link_blacklist, base_url):

    passlist = [l for l in links if not any(xl in l for xl in link_blacklist)] # Filtra links que contem texto constante na blacklist    
    filtered_list = []
    discarded_list = []
    
    for i in passlist:
        if (len(i) <= 1) or i == base_url: # Descarta se for so uma barra ou o url base do boticario
            discarded_list.append(i)
        elif i[:len(base_url)] == base_url: # Mantem se for um url do boticario
            filtered_list.append(i)
        elif i[:4] == 'http':
            discarded_list.append(i)
        elif i[0] == '/': # Monta o url completo
            filtered_list.append(base_url+i)
        elif i[0] != '/': # Monta o url completo
            filtered_list.append(base_url+'/'+i)
        else:
            discarded_list.append(i)

    return filtered_list


# In[ ]:


def get_filtered_links(seed_url, base_url, link_blacklist):
    r = session.get(seed_url)

    return filter_links(r.html.links, link_blacklist, base_url)


# In[ ]:


def link_type(session, link):
    try:
        page_type = link.split('/')[4].capitalize()

    except Exception as e:
        page_type = "Unknown"
        if debug_mode:print(e)
    
    if debug_mode:
        print("Type: ", page_type)

    return page_type


# In[ ]:


def new_link(link, product_set, discard_set): # Verifica se o link ja foi visto ou nao
    new = not(link in product_set or link in discard_set)
    
    return new


# In[ ]:


def get_product_links(session, link):

    r = session.get(link)
    soup = BeautifulSoup(r.text, "html.parser")

    lks = []
    pods = soup.find_all("div", {"pod-layout":"4_GRID"})

    for pod in pods:
        a = pod.find("a", {"class":"jsx-2907167179 layout_grid-view layout_view_4_GRID"}).attrs['href']

        if link_type(session, a) == "Product":
            lks.append(a)

    return lks


# In[ ]:


def product_mapper(session, seed_links, link_type_blacklist, link_blacklist, product_max):
    product_set = set() # Pilha de produtos
    discard_set = set() # Pilha de descarte
    seed_set = set(seed_links) # Pilha de links
 
    while (len(seed_set) > 0) and (len(product_set) < product_max):
        link = seed_set.pop() # Pega o primeiro link da lista
        
        if debug_mode:
            print("---------------------------------------")
            print("Product stack: ", len(product_set))
            print("Discard stack: ", len(discard_set))
            print("Link stack: ", len(seed_set))
            print("Current link: ", link)
        
        p_links = get_product_links(session, link)
        
        old_size = len(product_set)       

        for p in p_links: # Adiciona todos os produtos da pagina na pilha de produtos
            product_set.add(p)

        new_size = len(product_set)

        if debug_mode:
            print(new_size-old_size, " new links added to product stack")

        discard_set.add(link)
    
    return product_set


# # Pegando dados de um único produto
# 
# Dados desejados:
# - País
# - Concorrente
# - Data scrape
# - ID produto
# - Título
# - Descrição
# - Preço atual
# - Preço antigo
# - Desconto atual
# - Moeda
# - Disponibilidade
# - Condição
# - Departamento
# - Categoria
# - Marca
# - Linha
# - URL

# In[ ]:


def get_item_data(session, link): # A partir da pagina do item, busca todas suas informacoes pertinentes
    r = session.get(link)
    
    item = BeautifulSoup(r.text, "html.parser")
    
    pais = "Chile"
    competidor = "Falabella"
    data = date.today().strftime("%d/%m/%Y")

    # ID
    try:
        id = link.split('/')[-1]
    except Exception as e:
        id = None
        if debug_mode:print(e)

    # Title
    try:
        title = item.head.find("meta", {"property":"og:title"}).attrs['content'].split('|')[0].strip()
    except Exception as e:
        title = None
        if debug_mode:print(e)
        
    # Description
    try:
        description = item.head.find("meta", {"name":"description"}).attrs['content']
    except Exception as e:
        description = None
        if debug_mode:print(e)
        
    # Current price
    try:
        price = item.find("li", {"class":"jsx-749763969 prices-0"}).attrs['data-event-price'].replace('.','')
        price = int(price)
    except Exception as e:
        price = None
        if debug_mode:print(e)
        
    # Previous price
    try:
        maxprice = item.find("li", {"class":"jsx-749763969 prices-1"}).attrs['data-normal-price'].replace('.','')
        maxprice = int(maxprice)
    except Exception as e:
        maxprice = None
        if debug_mode:print(e)
        
    # Currency
    try:
        currency = 'CLP'
    except Exception as e:
        currency = None
        if debug_mode:print(e)
        
    # Seller
    try:
        seller = item.find("a", {"id":"testId-SellerInfo-sellerName"}).attrs['href'].split('/')[-1]
        seller = unquote(unquote(seller))
    except Exception as e:
        seller = None
        if debug_mode:print(e)
        
    # URL
    url = link

    # Other attributes
    try:
        attrs = item.find_all("tr", {"class":"jsx-428502957"})
        tempDict = {}
        for att in attrs:
            k = att.contents[0].text
            v = att.contents[1].text
            tempDict[k] = v

    except Exception as e:
        tempDict = {}
        if debug_mode:print(e)    

    d = {	
            "País":pais,
            "Concorrente":competidor,
            "Data scrape":data,
            "ID produto":id,
            "Título":title,
            "Descrição":description,
            "Preço atual":price,
            "Preço antigo":maxprice,
            "Moeda":currency,
            "Vendedor":seller,
            "URL":url
        }

    d.update(tempDict) # Inclui demais atributos

    return pd.Series(d)


# In[ ]:


def get_all_items(session, links):
    df = pd.DataFrame()
    for link in links:
        try:
            item_data = get_item_data(session, link)
            df = df.append(item_data, ignore_index=True)
        except Exception as e:
            if debug_mode: print(e)
    return df


# # Função Main

# In[ ]:


def main(max_pages = 200, product_max = 10_000_000):

    session = HTMLSession()
    #asession = AsyncHTMLSession()
    base_url = "https://www.falabella.com"
    seed_url = "https://www.falabella.com/falabella-cl/category/cat7660002/Belleza--higiene-y-salud"

    link_blacklist = []
    link_type_blacklist = ['Unknown']

    
    # Scraping
    seed_links = []
    for i in range(1, max_pages+1):
        j = seed_url + '?page=' + str(i)
        seed_links.append(j)
    
    products = product_mapper(session, seed_links, link_type_blacklist, link_blacklist, product_max)

    df = get_all_items(session, products)
    
    # Reordenando
    first = ['País', 'Concorrente', 'Data scrape', 'ID produto', 'Título', 'Descrição', 'Preço atual', 'Preço antigo', 'Moeda', 'Vendedor', 'URL'] 
    cols = first + sorted([c for c in df.columns.to_list() if c not in first])   

    try:
        df = df[cols]
    except Exception as e:
        if debug_mode: print(e)
    
    df.to_excel("../02_Results/"+date.today().strftime("%Y_%m_%d")+"_"+"falabella.xlsx")


# In[ ]:


if __name__ == "__main__":
    main()

