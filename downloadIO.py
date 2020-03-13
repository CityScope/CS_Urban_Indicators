import requests
import pandas as pd
import zipfile
import os
from io import BytesIO
from pathlib import Path
from APICalls import fetch

IO_PATH  = 'tables/IO' 

Path(IO_PATH).mkdir(parents=True, exist_ok=True)

base_url = 'https://www.bls.gov/oes/special.requests/oesm{}in4.zip'
base_fname = 'oesm{}in4/nat4d_M{}_dl.xlsx'

year = '2018'
url = base_url.format(year[-2:])
fname = base_fname.format(year[-2:],year)
if not os.path.isfile(os.path.join(IO_PATH,fname)):
	r = fetch(url)
	if r.status_code==200:
		zipdata = BytesIO()
		zipdata.write(r.content)
		with zipfile.ZipFile(zipdata) as zip_ref:
			zip_ref.extract(fname,path=IO_PATH)
		df = pd.read_excel(os.path.join(IO_PATH,fname))
		df.to_csv(os.path.join(IO_PATH,os.path.splitext(fname)[0]+'.csv'))