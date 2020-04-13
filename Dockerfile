FROM jonduckworthdg/geopandas-base
COPY . /CS_Urban_Indicators
WORKDIR /CS_Urban_Indicators
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
CMD python ./listen.py