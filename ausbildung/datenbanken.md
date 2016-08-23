# Datenbanken

Für diese Aufgaben gehen wir davon aus, das die Azubis im zweiten oder dritten Lehrjahr sind und bereits die langweilen und nutzlosen Dinge wie Normalformen gelernt haben und mittlerweile ein Gefühl für ihre relationale Datenbank haben.

## Kontext aufbauen

### Relationales Modell im Vergleich zu dessen Vorgaengern.

@article{Codd:1982:RDP:358396.358400,
 author = {Codd, E. F.},
 title = {Relational Database: A Practical Foundation for Productivity},
 journal = {Commun. ACM},
 issue_date = {Feb 1982},
 volume = {25},
 number = {2},
 month = feb,
 year = {1982},
 issn = {0001-0782},
 pages = {109--117},
 numpages = {9},
 url = {http://doi.acm.org/10.1145/358396.358400},
 doi = {10.1145/358396.358400},
 acmid = {358400},
 publisher = {ACM},
 address = {New York, NY, USA},
 keywords = {data integrity, data manipulation, data structure, database, productivity, relational database, relational model},
 }

Codd war der Vater des relationalen Modells (https://en.wikipedia.org/wiki/Relational_model). Datieren kann man das RM auf 1970. Der Artikel ist Codds Perspektiver auf das relationale Modell, 12 Jahre nach dessen Erstpublikation. Der Artikel stellt die Rede anlaesslich der Verleihung des Turing Preises an ihn dar.

### Relationales Modell heute im Verlgeich zu neueren Systemen

@article{Helland:2016:SSS:2975594.2948983,
 author = {Helland, Pat},
 title = {The Singular Success of SQL},
 journal = {Commun. ACM},
 issue_date = {August 2016},
 volume = {59},
 number = {8},
 month = jul,
 year = {2016},
 issn = {0001-0782},
 pages = {38--41},
 numpages = {4},
 url = {http://doi.acm.org/10.1145/2948983},
 doi = {10.1145/2948983},
 acmid = {2948983},
 publisher = {ACM},
 address = {New York, NY, USA},
 }

Helland ist Industrie-Veteran, hat seit den 80ern an relationalen und arbeitet seit Mitte der 2000er Jahre mit verteilten Systemen und aeussert sich ueber die deutlichen Staerken von SQL, aber auch dessen Schwaechen.

### NoSql & NewSql

Spanner & F1

### Hybrid Transactional Analytical Processing

http://hyper-db.de/


## Parallelitaet

Erlaeterung der Serialisierbarkeit (bereits eingefuhert in Helland:2016). Umsetzung mit MVCC (MSSQL und PG).


## Performance

Erlaeuterung, wozu Indizes gut sind. In-memory join vs. temp. Tabellen. Praxis: Index-Nutzung, Buffer Hitrate und Join Order.

```
log_slow_queries  = /var/log/mysql/mysql-slow.log
long_query_time  = 1
log-queries-not-using-indexes
```

### Index Nutzung

```
EXPLAIN EXTENDED
select foo from bar inner join boz on bar.froboz = boz.frobnik
\G;
```

`Explain extended` gibt den query plan aus, `\G` sorgt dafuer das die
Ausgabe besser lesbar ist.


### Buffer / Cache

Cache Hit Rate. Datenbank Buffer vs. OS Buffer. Groessenunterschied
zwischen Hauptspeicher und Festplatte.

https://www.percona.com/blog/2007/11/03/choosing-innodb_buffer_pool_size/


### Join Order Benchmark

@article{Leis:2015:GQO:2850583.2850594,
 author = {Leis, Viktor and Gubichev, Andrey and Mirchev, Atanas and Boncz, Peter and Kemper, Alfons and Neumann, Thomas},
 title = {How Good Are Query Optimizers, Really?},
 journal = {Proc. VLDB Endow.},
 issue_date = {November 2015},
 volume = {9},
 number = {3},
 month = nov,
 year = {2015},
 issn = {2150-8097},
 pages = {204--215},
 numpages = {12},
 url = {http://dx.doi.org/10.14778/2850583.2850594},
 doi = {10.14778/2850583.2850594},
 acmid = {2850594},
 publisher = {VLDB Endowment},
}

Downloads:
 - ftp://ftp.fu-berlin.de/pub/misc/movies/database/
 - http://www-db.in.tum.de/~leis/qo/job.tgz
 - imdbpy (bei Arch als Paket installieren ansonsten `pip ...`)


