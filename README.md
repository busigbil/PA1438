# Beskrivning
Detta projekt har skapats för kursen PA1438 på BTH. Syftet är att modellera de väntetider som en användare kan uppleva då många samtidiga användare kan logga in, och var dessa väntetider kan uppträda.

## Visualisering av inloggning
![Login app](imgs/login_formv2.gif)

Projektet innehåller filer för att sätta upp en enkel login-applikation, belasta applikationen med samtidiga användare som loggar in, samt mäta svarstider och resursbelastningen.

Projektet är uppdelat i:
- Applikationen med login-funktionen.
- Locust-skriptet som simulera samtidiga användare som loggar in i applikationen.
- Databasen med användarens uppgifter, som används både av applikationen och Locust-skriptet.

## Sekvensdiagram för projektet
![sekvensdiagram](imgs/sekvensdiagramV2.png)

## Login-app
Login-applikationen har byggts i Flask, och innehåller router för index, login och home:
- Index-routen: Renderar ett HTML-formulär där användaren anger användarnamn och lösenord. Uppgifterna skickas med HTTP POST-anrop till login-routen.
- Login-routen: Tar emot användarens login-uppgifter och verifierar dem. Användarens uppgifter hämtas från databasen, och lösenordet autentiseras med hashing-algoritmen Bcrypt. När uppgifterna har autentiserats, uppdateras databasen med tidsstämpel för senaste inloggning. Användarens uppgifter skrivs till session, och användaren dirigeras sedan till home-routen.
- Home-routen: Renderar användarens inloggade HTML-sida, hämtar användarens uppgifter från session och visar upp på sidan.

### Bcrypt och kostnadsfaktor
Alla användares lösenord har lagrats i databasen som bcrypt-hashar med kostnadsfaktor 10. Hashen innehåller både salt och kostnadsfaktor. När lösenordet verifieras används samma salt och kostnadsfaktor för att hasha lösenordet som användaren använt vid inloggning, och jämför detta med den lagrade lösenords-hashen från databasen.

Bcrypt är avsiktligt beräkningstungt för att försvåra lösenords-attacker. Kostnadsfaktorn är en exponent som styr hur tung beräkningen är. Faktor 10 innebär att bcrypt kör krypteringsprocessen 2^10 (1024) varv efter varandra. Det påverkar både exekveringstiden och CPU-belastningen. Varje hashning är CPU-bunden och enkeltrådad, och upptar en CPU-kärna medan den pågår.

## Webbserver
Projektet använder Gunicorn tillsammans med Nginx för att serva Flask-applikationen. Nginx är en webbserver som ligger framför Gunicorn och tar emot och vidarebefordrar alla HTTP-anrop som anländer från Locust. Gunicorn är en Python Web Server Gateway Interface (WSGI) server, vilket innebär att den tar emot HTTP-anrop från Nginx, och översätter dem till WSGI-formatet som Flask-applikationen kan hantera, så att applikationen kan köras och returnera ett svar. 

Tanken med projektet är att vara produktionslikt, utan medvetet inbyggda felkällor som kan försämra prestandan vid högre belastningsnivåer. Därför används Gunicorn och Nginx istället för Pythons inbyggda utvecklingsserver, eftersom denna inte är utformad för att hantera högre belastning, eller flera samtidiga work-processer. I Gunicorn är det möjligt att styra hur många anrop som kan hanteras parallellt, exempelvis genom att konfigurera antal workers och trådar. 

Eftersom verifieringen med bcrypt upptar CPU-kärnor vid hashning, anpassas antalet workers utifrån tillgängliga CPU-kärnor. Med den tillgängliga hårdvaran motsvarar detta fyra workers. Eftersom applikationen även utför flera I/O-operationer, som databasanrop, använder projektet Gunicorns worker-typ gthreads. Gthreads möjliggör för flera trådar per worker, där varje tråd kan hantera ett anrop. För att förhindra att inkommande anrop fastnar i Gunicorns backlog i ett tidigt skede, har antalet trådar per worker satts till sex stycken. 

Projektets kombination av workers och trådar innebär att maximalt 4 workers * 6 trådar = 24 anrop kan hanteras samtidigt inuti applikationen. Om en ny anslutning görs när alla workers är upptagna, kommer den att hamna i Gunicorns backlog. Som storlek på Gunicorns backlog används standardvärdet på 2048. Om antalet anslutningar i backlog överstiger 2048, kommer nya klienter som försöker ansluta få ett felmeddelande. För att säkerställa att workers inte fastnar, använder Gunicorn timeout. I projektet används Gunicorns standard timeout om 30 sekunder. Det innebär att en worker som har varit stilla i 30 sekunder kommer att avbrytas och starta om. 

## Locust-skript
För att belasta inloggningsapplikationen med samtidiga användare används Python-biblioteket Locust. Testskriptet är utformat för att simulera ett specificerat antal virtuella användare som skickar anrop till en given route. Inledningsvis hämtas samtliga användarnamn från databasen och lagras i en lista. Vid varje nytt inloggningsförsök väljs ett slumpmässigt användarnamn från listan. För enkelhets skull har alla användare samma lösenord.

Varje användare som skapas i Locust fungerar som en egen isolerad webbläsare. De cookies som skapas under sessionen sparas till den specifika användaren. I slutet av varje inloggningflöde rensar skriptet cookies, så att dessa inte skickas automatiskt i nästkommande flöden. 

För att minska risken för att Locust utgör en flaskhals körs belastningstesterna i distribuerat läge med en master-process och flera worker-processer. Applikationen förväntas bli mättat vid en relativt låg nivå av samtidiga användare, därför bedöms den valda konfigurationen vara tillräcklig för testernas syfte. 

## Databas
Som databashanterare används PostgreSQL, och databasen skapas i Docker-containern utifrån Postgres officiella Docker-image. Den innehåller en tabell med användarens uppgifter, såsom namn, användarnamn, hashat-lösenord, och tidsstämpel för senaste inloggning. Databas-tabellen seedas med användaruppgifter som genereras med Pythons Faker-bibliotek, samt hashade-lösenord. 

Databasen används i Locust-skriptet för att hämta användarnamn att logga in med. Databasen används också i applikationen för att hämta användarens uppgifter, och för att uppdatera tabellen med tidsstämpel för senaste inloggning.

Databasanslutningarna hanteras med hjälp av psycopg2-anslutningspool. En anslutningspool är en samling återanvändbara databasanslutningar, där applikationen som ska utföra en databasoperation lånar en anslutning, utför databasoperationen och lämnar tillbaka anslutningen. Eftersom projektet använder en webbserver i flertrådat läge, används klassen ThreadedConnectionPool, där anslutningspoolen kan delas av flera trådar.

Varje Gunicorn worker motsvarar en egen process, med en egen databaspool. Därför konfigureras databaspoolens storlek utifrån antalet trådar som varje worker har, det vill säga sex trådar. Med fyra workers innebär det att 4 * 6 = 24 anslutningar maximalt förväntas göras mot databasen samtidigt. 

## Hårdvara och nätverk
Projektet körs i Docker-containrar på tre maskiner: en maskin för Locust, en för Flask-applikationen, och en för databasen. Docker-containrarna har tillgång till följande hårdvara på värdmaskinerna: 
- Locust-maskinen har en processor av modellen AMD Opteron 4386 med åtta kärnor och en tråd per kärna. Maskinen har 32 GB RAM, varav ca. 30 GiB är tillgängligt i Ubuntu. 
- Applikationens maskin har en processor av modellen Intel Xeon E3-1220 V2, med fyra kärnor och en tråd per kärna. Maskinen har 8 GB RAM, varav 7,2 GiB är tillgängligt i Ubuntu.
- Databasens maskin har en processor av modellen AMD Opteron 4334, med sex kärnor och en tråd per kärna. Maskinen har 32 GB RAM, varav ca. 30 GiB är tillgängligt i Ubuntu. 

Alla maskiner är geografiskt placerade på Blekinge Tekniska Högskola och är uppsatta inom ett privat nätverk som nås genom en bastionserver. Trafiken routas från Locust-maskinen via applikationens maskin till databasens maskin genom två separata subnät. I applikationsmaskinen används VLAN-uppdelning på samma fysiska nätverksport för att separera trafiken mellan de två subnäten. 

Alla maskiner är utrustade med gigabit-nätverkskort med full duplex. Maskinerna som kör Locust och applikationen har en länkhastighet på 100 Mbps, medan nätverkskortet på maskinen som kör databasen har en länkhastighet 1000 Mbps. Eftersom applikationsmaskinen delar bandbredd mellan inkommande och utgående trafik, innebär det i praktiken att den effektiva bandbredden är närmare 50 Mbps.

Samtliga maskiner kör operativsystemet Ubuntu 26.04.1 LTS (64-bitars, x86_64) med Linux-kärna 7.0.0-43-generic.


# Installation
För att köra projektet behöver Docker och Chrony vara installerat på alla maskiner. Dessutom ska en DPMI-mätpunkt sättas upp, för att kunna mäta nätverkstrafiken. Nedan beskrivs hur Docker och Chrony kan installeras med hjälp av Ansible-playbooks, som finns tillgängliga i katalogen som heter Ansible.

## Ansible
Ansible är en automations-plattform som används för konfigurationshantering, applikationsdistribution och orkestrering av IT-miljöer. Med hjälp av Ansible kan projektet styras från en separat dator, eftersom Ansible kommunicerar direkt med maskinerna genom SSH-protokoll. 

Ansible behöver inte installeras på maskinerna som kör projektet, däremot behöver det vara installerat på maskinen som ska köra Ansible. 

En utförlig beskrivning för att installera Ansible finns på: [Ansible docs](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html)

För att installera Ansible på Ubuntu körs följande kommandon:
```console
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install ansible
```

Installera de samlingar som playbooks behöver:
```console
ansible-galaxy collection install community.general community.docker
```
Verifiera att allt har installerats korrekt:
```console
ansible --version
ansible-galaxy collection list
```
För att kunna köra Ansible-playbooks behöver SSH och autentisering vara konfigurerade för fjärrmaskinerna, samt ska korrekta IP-adresser till maskinerna anges i filen inventory.yml  

Testa att Ansible når maskinerna genom att köra: 
```console
ansible all -i inventory.yml -m ping
```

## Docker 
Docker Engine är en container-teknologi som möjliggör för att köra en applikation och alla dess beroenden inom en isolerad miljö (container). Projektet förutsätter att Docker Engine finns installerat på alla maskiner, eftersom alla delar körs i Docker-containrar. 

En utförlig beskrivning om hur Docker installeras på Ubuntu finns på: [Docker docs](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository )

Installera Docker genom att köra den Ansible-playbook som installerar Docker och Docker compose på alla maskiner:
```console
ansible-playbook -i inventory.yml install-docker.yml
```
Verifiera att Docker har installerats korrekt:
```console
ansible all -i inventory.yml -m command -a "docker compose version"
```

I katalogen för Deploy finns docker-compose-filer för att starta projektet på tre separata maskiner. Alla docker-compose-filer utgår från existerande publika Docker-images. Nya Docker-images kan byggas utifrån de Docker-filer som finns i respektive katalog för App, Database, Locust. I maskinen som kör applikationen ska separata Docker-containrar köras för Nginx och en för Gunicorn + Flask. För att kunna köra projektet behöver korrekta IP-adresser för varje host anges som environment-variablar i respektive fil.

Docker-compose-filen för databasen kommer att skapa en databas-tabell utifrån det schema som finns i filen schema.sql, i katalogen Database. Tabellen kommer fyllas med användar-uppgifter utifrån seed-skriptet som finns i samma katalog. 

## Chrony
Chrony är ett protokoll som bygger på Network Time Protocol (NTP), och används för att synkronisera klockor över ett nätverk. Chrony installeras på alla maskiner, eftersom klockorna på de olika maskinerna behöver vara synkroniserade, så att maskinenrnas resursutnyttjande kan jämföras. För att synkronisera klockorna mellan maskinerna, ska en maskin sättas upp som en NTP-server, medan de andra är NTP-klienter. För projektet används maskinen som kör Locust som NTP-server, medans maskinerna som kör applikationen och databasen är klienter.

Installera Chrony genom att köra Ansible-playbook:
```console
ansible-playbook -i inventory.yml install-chrony.yml
```
Kontrollera att tjänsten chrony är aktiv:
```console
systemctl status chrony
```
Verifiera tidssynkroniseringen:
```console
chronyc tracking
chronyc sources -v
```

## Distributed Passive Measurement Infrastructure
Distributed Passive Measurement Infrastructure (DPMI) är ett ramverk för nätverksövervakning som använder sensorer utplacerade över flera nätverksdomäner för att samla in, bearbeta och analysera pakettrafik. 

I labbmiljön placeras en DPMI-mätpunkt mellan Locust och applikationsservern för att mäta nätverkstrafiken. Eftersom den mäter både anrop och svar med samma klocka kan serverns totala svarstid mätas utan klocksynkronisering. Resultatet kan jämföras med Locusts svarstid och Flasks route-tid. Mätpunkten kan även upptäcka TCP-problem, exempelvis SYN-retransmissioner vid full backlog. 

# Testkörning
Innan testkörningarna påbörjas, initieras systemmiljön genom att docker-compose-filer distribueras och startas på respektive maskin. Detta automatiseras med en Ansible-playbook som kopierar konfigurationsfilerna och startar upp Docker-containrarna på respektive maskin.

Kör den Ansible-playbook som kopierar Docker-compose-filerna och startar containrarna: 
```console
ansible-playbook -i inventory.yml deploy.yml
```

För att genomföra belastningtesterna används en separat Ansible-playbook: run-test.yml. Denna playbook interagerar med Locust API via dess webbgränssnitt. IP-adressen till maskinen som kör Locust ska anges i anropssträngen. Testets belastningsprofil konfigureras i anropets payload med följande parametrar:

- user_count: totala antalet samtidiga virtuella användare
- spawn_rate: accelerationstakt (antal användare som läggs till per sekund under uppvärmningsfasen).
- run_time: testets totala körtid, inklusive tiden för upptrappning och nedtrappning.

Genom att uppdatera dessa parametrar kan systemet utvärderas utifrån de fyra belastningsnivåer som beskrivs nedan. För att få minimera effekter av outlier-värden och få tillförlitliga genomsnittsvärden för genomströmning och svarstider, upprepas testkörningarna för varje belastningsnivå tre gånger. 

Uppdatera belastningsuppgifterna och kör Ansible playbook. Ange ett testid som används för att märka upp katalogen med testloggar för respektive körning:
```console
ansible-playbook run-test.yml -e "run_id=test_001"
```

## Locust webbgränssnitt
![Locust UI](imgs/locust_ui.png)


## Belastningsnivåer
För att se hur systemet påverkas av belastning, utförs testerna under fyra belastningsnivåer:
- Låg belastning: En nivå som används för att fastställa en baslinje för svarstider och genomströmning.
- Optimal belastning: En nivå där systemet uppnår hög genomströmning utan att svarstiderna ökar markant. 
- Hög belastning: En nivå där systemet närmar sig sin kapacitetsgräns, vilket kan medföra ökande svarstider trots att genomströmningen fortfarande ökar eller ligger kvar nära sin maximala nivå.
- Överbelastning: En nivå där systemet inte längre kan hantera den inkommande belastningen med acceptabel prestanda. Detta kan medföra kraftigt ökade svarstider, fler felaktiga anrop eller minskad genomströmning.

Inför mätningarna görs en teoretisk överslagsberäkning för att uppskatta vid vilken belastning systemet kan förväntas nå sin kapacitetsgräns. Beräkningen baseras på den uppskattade CPU-tiden för bcrypt-hashning, antalet tillgängliga CPU-kärnor och Littles sats. Syftet är att få en teoretisk referens för val av belastningsnivåer och förväntad systemkapacitet. Efter mätningarna jämförs uppskattningen med de uppmätta svarstiderna och genomströmningen, för att undersöka hur väl beräkningen överensstämmer med systemets faktiska beteende.

### Littles sats
För att uppskatta antalet samtidiga användare som skickar anrop används Littles sats, som beskriver sambandet mellan genomströmning, svarstid och det genomsnittliga antalet anrop:

$$N= \lambda \times W $$

Där ($N$) är det genomsnittliga antalet användare i systemet, ($\lambda$) är genomströmningen i anrop per sekund och ($W$) är den genomsnittliga tiden ett anrop tillbringar i systemet. Resultatet beskriver alltså det genomsnittliga antalet samtidiga anrop som systemet hanterar.

### Teoretisk kapacitet
Eftersom bcrypt-hashningen är CPU-bunden förväntas den begränsa systemets maximala genomströmning. Med en uppskattad CPU-tid på 0,1 sekunder per hashning kan en CPU-kärna hantera maximalt 10 hashningar per sekund. Med fyra CPU-kärnor blir den teoretiska maximala genomströmningen därmed 40 anrop per sekund:

$$\lambda_{max} = \frac{4}{0,1} = 40\ \text{anrop/s}$$

För att uppskatta svarstiden används antaganden om både CPU-bunden bearbetning och I/O-väntan. I projektet förväntas bcrypt-hashning utgöra en betydande del av den CPU-bundna bearbetningen. Med den valda kostnadsfaktorn uppskattas hashningstiden till cirka 0,1 sekunder per anrop. Därutöver uppskattas den sammanlagda I/O-väntan, exempelvis för nätverkskommunikation och databasanrop, till cirka 0,05 sekunder Den uppskattade totala svarstiden blir därmed 0,15 sekunder per anrop.

Locus-testet utgör ett slutet system där varje användare antas skicka ett anrop, invänta svaret och därefter vänta mellan 1 och 3 sekunder innan nästa anrop skickas. I ett slutet system ska även väntetiden mellan anropen tas med i beräkningen, för att få en uppskattning om den genomsnittliga tiden för hela anropscykeln. Med en genomsnittlig väntetid på 2 sekunder beräknas den genomsnittliga tiden som ett anrop tillbringar i systemet till 2,15 sekunder:

$$W = 0,15 + 2 = 2,15s$$

Utifrån en genomsnittlig total svarstid på 2,15 sekunder och genomströmningen om 40 anrop per sekund, kan den uppskattade belastningen beräknas med Littles sats:

$$N = 40 \times 2,15 = 86\ \text{användare}$$

Beräkningen beskriver det förväntade antalet samtidiga anrop som systemet uppskattas kunna hantera.


### Val av belastningsnivåer
Med utgångspunkten att 86 samtidiga användare är den teoretiskt optimala belastningen, definieras belastnings-nivåerna nedan:
- Låg belastning: 6 användare
- Optimal belastning: 86 användare
- Hög belastning: 100 användare
- Överbelastning: 500 användare

# Datainsamling
Vid varje testkörning per belastningsnivå samlas data med loggade svarstider och resursanvändning in. Datan som samlas in beskrivs nedan.

Kör Ansible playbook för att samla in testdata och spara till en katalog med samma test id som testkörningen:
```console
ansible-playbook fetch-logs.yml -e "run_id=test_001"
```

## Loggning
I Locust-skriptet loggas data för varje anrop som skickas, och sparas i en .jsonl fil. I Locust genereras ett anrops-id som följer med till loggningen i Login-applikationen, så att svarstiden i Locust kan jämföras med exekveringstiden för applikationen. 
Datan som loggas i Locust är:
- Anrops-id
- Starttid för anrop
- Namn på route som anrop skickas till
- Svarstid, alltså tiden från att anropet skickats till att svar kommer tillbaka
- Eventuella exceptions

Nginx har konfigurerats för att logga webbserverns inbyggda tidsvariabler för varje route i JSON-format, tillsammans med tidsstämpel och anrops-id som följer med från Locust. Följande data loggas i Nginx: 
- Upstream Connect ms: tiden i millisekunder för att upprätta en nätverksanslutning mellan Nginx och Gunicorn
- Upstream Header ms: tiden i millisekunder för att ta emot den allra första byten av HTTP-headern med svaret från Gunicorn, inkluderat exekveringstiden för Flask
- Upstream Response ms: tiden i millisekunder för att ta emot hela svaret från Gunicorn, inkluderat exekveringstiden för Flask, från första anslutnignen, till att hela svaret har mottagits
- Request ms: den totala tiden i millisekunder för anropet att hanteras av Nginx, från att anropet ankommer till Nginx till att svaret skickas tillbaka.
  
För login-applikationen loggas den totala tiden för att exekvera varje route med Python-biblioteket logger. Loggarna sparas till en jsonl-fil. För login-routen loggas utöver den totala tiden för att exekvera routen även följande data:
- Tid för att göra SELECT-anrop till databasen
- Tid för att göra UPDATE-anrop till databasen
- Tider för att ansluta till databas-pool för SELECT och UPDATE-anrop
- Tid för att verifiera hashat lösenord med Bcrypt.

## Resursmätning
För att mäta resursutnyttjande på de tre maskinerna används dedikerade Bash-skript. Skripten extraherar prestandadata direkt från Linux kontrollgrupper (cgroups) för varje container, samt från världssystemets globala räknare i /proc. 

Cgroups (Control Groups) är en funktion i Linux-kärnan som isolerar och övervakar resursutnyttjandet för specifika processgrupper, vilket i detta projekt används för att extrahera CPU- och minnesdata för varje enskild Docker-container. Det virtuella filsystemet /proc fungerar som ett gränssnitt direkt mot Linux-kärnan, och används här för att samla in prestandaräknare för värddatorns systemhälsa.

Mätdata samlas in vid två tidpunkter, för att isolera testets stabila fas. Det första stickprovet tas direkt efter att uppvärmningsfasen är slutförd, och antalet samtidiga användare har uppnåtts. Det andra stickprovet tas precis innan nedtrappningen av användare påbörjas.

Genom att beräkna skillnaden mellan det slutliga och det inledande stickprovet fås ett mått på resursförbrukningen under den stabila mätperioden. Utifrån detta mått beräknas systemets nyttjandegrad ($\rho$) enligt följande formel:

$$\rho = \frac{\text{Uppmätt CPU-tid}}{\text{Mätperiodens längd x Antal CPU-kärnor}}$$

Datainsamlingen för resursutnyttjande är automatiserad via den Ansible-playbook kör testerna, och triggar Bash-skripten vid uppvärmningens slut samt vid testets slut. Skripten skriver sedan resursdata direkt till json-filer med tillhörande tidsstämplar. 

## Nätverksmätning
...

## Sekvensdiagram med mätpunkter
![Sequence diagram with measurement points](imgs/measure_diagram.png)




