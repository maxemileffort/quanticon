Template:
```
python "script snippets/bento_ingestion_prep.py" --input <path to bento_file.csv> --output <path to bento_file.csv root/mt5_<symbol>.csv>
```

Example:
```
python "script snippets/bento_ingestion_prep.py" --input "C:\Users\Max\Downloads\nq_bento\data\glbx-mdp3-20160121-20260221.ohlcv-1m.csv\glbx-mdp3-20160121-20260221.ohlcv-1m.csv" --output "C:\Users\Max\Downloads\nq_bento\data\mt5_nq.csv"
```

Template
```
python "script snippets/mt5_outright_merge.py" --input-dir <dir with data>
```

Example:
```
python "script snippets/mt5_outright_merge.py" --input-dir "C:\Users\Max\Downloads\nq_bento\data"
```