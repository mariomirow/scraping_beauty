#!/usr/bin/env python
# coding: utf-8

# In[1]:


import numpy as np
import pandas as pd
from requests_html import HTMLSession
from bs4 import BeautifulSoup
from datetime import date
import re
import json


# In[ ]:


debug_mode = False


# # Mapeando a árvore de URLs

# In[2]:


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


# In[3]:


def get_filtered_links(session, seed_url, base_url, link_blacklist):
    r = session.get(seed_url)

    return filter_links(r.html.links, link_blacklist, base_url)


# In[4]:


def link_type(session, link):
    r = session.get(link)
    soup = BeautifulSoup(r.text, "html.parser")
    page_type = 'Unknown'

    try:
        script = soup.find_all("script")[1]
        pattern = re.compile("blz.pageType = (.*?);") # Acha essa variavel entre os elementos com tag script
        page_type = pattern.findall(script.string)[0].replace("'","") # Remove aspas simples do texto

    except Exception as e:
        if debug_mode: print(e)
    
    return page_type


# In[5]:


def new_link(link, product_set, discard_set): # Verifica se o link ja foi visto ou nao
    new = not(link in product_set or link in discard_set)
    
    return new


# In[6]:


def product_mapper(session, base_url, seed_links, link_type_blacklist, link_blacklist, product_max):
    product_set = set() # Pilha de produtos
    discard_set = set() # Pilha de descarte
    seed_set = set(seed_links) # Pilha de links
 
    while (len(seed_set) > 0) and (len(product_set) < product_max):
        link = seed_set.pop() # Pega o primeiro link da lista
        new = new_link(link, product_set, discard_set)
        
        if debug_mode:
            print("---------------------------------------")
            print("Product stack: ", len(product_set))
            print("Discard stack: ", len(discard_set))
            print("Link stack: ", len(seed_set))
            print("Current link: ", link)
            print("New link: ", new)

        if new: # Continua so se for um link novo
            lk_type = link_type(session, link) # E pega seu tipo

            if debug_mode:
                print("Link type: ", lk_type)

            if lk_type not in link_type_blacklist: # Continua so se nao for um dos tipos no blacklist,

                if lk_type == "Produto": # Se for um produto
                    product_set.add(link) # Coloca na pilha de produtos
                    
                    if debug_mode:
                        print("Link added to product stack")

                else: # Se nao for um produto (pode ser Categoria, SubCategoria, Landing, Linha, Marca, etc.)
                    potential_links = get_filtered_links(session, link, base_url, link_blacklist) # Lista os links dentro dele
                    
                    new_links = [l for l in potential_links if new_link(l, product_set, discard_set)] # Destes, pega apenas os novos
                    
                    old_size = len(seed_set)
                    for nl in new_links:            
                        seed_set.add(nl) # Adiciona links novos aa lista principal
                    new_size = len(seed_set)

                    if debug_mode:
                        print(new_size-old_size, " new links added to link stack")

        discard_set.add(link) # Adiciona link que acabamos de ver aa pilha de descarte

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

# In[7]:


def get_item_data(session, link): # A partir da pagina do item, busca todas suas informacoes pertinentes
    r = session.get(link)
    
    item = BeautifulSoup(r.text, "html.parser").head # Maior parte dos dados esta na seção 'head', sobe o 'parent' se precisar de algo de fora
    
    pais = "Brasil"
    competidor = "O Boticario"
    data = date.today().strftime("%d/%m/%Y")

    # Description
    try:
        description = item.find("meta", {"property":"og:description"}).attrs["content"]
    except Exception as e:
        description = None
        if debug_mode:print(e)
    
    # Availability
    try:
        availability = item.find("meta", {"property":"product:availability"}).attrs["content"]
    except Exception as e:
        availability = None
        if debug_mode:print(e)

    # Condition
    try:
        condition = item.find("meta", {"property":"product:condition"}).attrs["content"]
    except Exception as e:
        condition = None
        if debug_mode:print(e)

    # Price
    try:
        price = item.find("meta", {"property":"product:price:amount"}).attrs["content"]
        price = float(price)
    except Exception as e:
        price = None
        if debug_mode:print(e)

    # Currency
    try:
        currency = item.find("meta", {"property":"product:price:currency"}).attrs["content"]
    except Exception as e:
        currency = None
        if debug_mode:print(e)
    
    # ID
    try:
        id = item.find("meta", {"property":"product:retailer_item_id"}).attrs["content"]
    except Exception as e:
        id = None
        if debug_mode:print(e)

    # Title
    try:
        title = item.find("meta", {"property":"og:title"}).attrs["content"].split("|")[0].strip()
    except Exception as e:
        title = None
        if debug_mode:print(e)
        
    # URL
    try:
        url = item.find("meta", {"property":"og:url"}).attrs["content"]
    except Exception as e:
        url = None
        if debug_mode:print(e)
        
    # MaxPrice
    try:
        maxprice = item.parent.find("strong", {"class": "nproduct-price-max"}).s.text.strip().strip("R$").strip().replace(',','.')
        maxprice = float(maxprice)
    except Exception as e:
        maxprice = None
        if debug_mode:print(e)

    # Outros atributos
    pattern = re.compile("blz.globals.pageTree = (.*?);") # Acha essa variavel entre os elementos com tag script

    scripts = item.parent.find_all('script')[1] # Variável fica no segundo bloco 'script', serve para tracking do Google Tag Manager

    patt = pattern.findall(scripts.string)[0]
    attr = json.loads(patt) # Transforma em JSON para facilitar a conversao

    # Departamento
    try:
        departamento = attr['department']
    except Exception as e:
        departamento = None
        if debug_mode:print(e)
        
    # Categoria
    try:
        categoria = attr['category']
    except Exception as e:
        categoria = None
        if debug_mode:print(e)

    # Marca
    try:
        marca = attr['brand']
    except Exception as e:
        marca = None
        if debug_mode:print(e)
        
    # Linha
    try:
        linha = attr['brandLine']
    except Exception as e:
        linha = None
        if debug_mode:print(e)
        
    # Demais atributos
    try:
        atributos = attr['attributes'] # Esses aqui são um dict dentro do JSON, crio um novo dict simplificado a partir deste
        tempDict = {}
        for i in atributos:
            k = i['name']

            v = []
            for j in i['values']:
                v.append(j['name'])

            tempDict[k] = ",".join(v)
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
            "Disponibilidade":availability,
            "Condição":condition,
            "Departamento":departamento,
            "Categoria":categoria,
            "Marca":marca,
            "Linha":linha,
            "URL":url
        }

    d.update(tempDict) # Inclui demais atributos

    return pd.Series(d)


# In[8]:


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

# In[12]:


def main(product_max = 10_000_000):
    
    session = HTMLSession()
    base_url = "https://www.boticario.com.br"
    seed_url = "https://www.boticario.com.br/institucional/mapasite/"

    link_blacklist = ['atendimento','autenticacao','compre-pelo-whatsapp','institucional','minha-conta','nossa-historia','sacola','dicas-de-beleza','clube','?']
    link_type_blacklist = ['Institucional', 'Unknown', 'quiz-giftable']

    # Scraping
    seed_links = get_filtered_links(session, seed_url, base_url, link_blacklist)

    products = product_mapper(session, base_url, seed_links, link_type_blacklist, link_blacklist, product_max)

    df = get_all_items(session, products)
    
    # Reordenando
    first = ['País', 'Concorrente', 'Data scrape', 'ID produto', 'Título', 'Descrição', 'Preço atual', 'Preço antigo', 'Moeda', 'Disponibilidade', 'Condição', 'Departamento', 'Categoria', 'Marca', 'Linha', 'URL']
    cols = first + sorted([c for c in df.columns.to_list() if c not in first])   

    try:
        df = df[cols]
    except Exception as e:
        if debug_mode: print(e)
    
    df.to_excel("../02_Results/"+date.today().strftime("%Y_%m_%d")+"_"+"boticario.xlsx")


# In[ ]:


if __name__ == "__main__":
    main()

