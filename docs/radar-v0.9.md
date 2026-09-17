# Radar v0.9 — Engineering Foundation

## 1. Cel milestone'u

Radar v0.9 nie dodaje nowej funkcjonalności produktowej.

Celem tej wersji jest uporządkowanie istniejącego systemu tak, aby Radar przestał być projektem rozwijanym iteracyjnie przez jednego autora/agenta, a zaczął wyglądać jak kod produkcyjny, który może zostać przekazany innemu zespołowi developerskiemu.

Po zakończeniu v0.9 nowy developer powinien móc:

* sklonować repozytorium,
* zrozumieć jego strukturę,
* zrozumieć przepływ danych,
* uruchomić aplikację,
* uruchomić testy,
* zweryfikować środowisko,
* wykonać lokalny development check,
* zrozumieć gdzie dodać nową funkcjonalność,
* zrozumieć gdzie znajduje się Radar Core,
* zrozumieć gdzie znajdują się integracje ze źródłami,
* zrozumieć sposób działania validation corpus,
* zrozumieć strategię CI,
* zmienić kod bez konieczności poznawania historycznych rozmów z AI.

Repozytorium powinno wyglądać jak projekt, który może zostać przejęty przez profesjonalny zespół.

v0.9 jest więc milestone'em:

> **Architecture + Developer Experience + Testing + CI Foundation + Documentation**

a nie nowym feature release.

---

# 2. Główna zasada

Najważniejszym wymaganiem v0.9 jest:

> Refactor architecture without changing Radar behavior.

Istniejące zachowanie Radara powinno zostać zachowane.

Jeżeli obecny kod działa poprawnie, nie należy zmieniać jego semantyki tylko dlatego, że inne rozwiązanie wygląda bardziej elegancko.

Refactor ma poprawić:

* czytelność,
* odpowiedzialności modułów,
* kierunek zależności,
* testowalność,
* maintainability,
* developer experience,
* CI readiness.

Nie ma poprawiać produktu poprzez ukryte zmiany zachowania.

---

# 3. Zasady architektoniczne Radara

Poniższe zasady są częścią projektu i nie mogą zostać utracone podczas refactoru.

## 3.1 Evidence-first

Radar powinien móc wskazać źródło swoich wniosków.

Ważne informacje powinny zachowywać model:

```text
Fact
+
Evidence
+
Confidence
+
Context
```

Refactor nie może usunąć lub osłabić mechanizmu evidence.

---

## 3.2 UNKNOWN > guessing

Jeżeli Radar nie może wiarygodnie określić informacji:

```text
UNKNOWN
```

jest poprawnym wynikiem.

Nie należy zwiększać „inteligencji” systemu poprzez zgadywanie.

Precision pozostaje ważniejsze niż recall.

---

## 3.3 Deterministic core first

Podstawowe działanie Radara ma być deterministyczne.

AI może zostać dodane później jako:

* explanation layer,
* inference layer dla niejednoznacznych przypadków,
* natural language interface.

AI nie może zastępować deterministycznego core.

v0.9 nie dodaje żadnej warstwy AI.

---

## 3.4 Source-neutral Radar Core

GitHub jest obecnie głównym źródłem danych.

Nie powinien jednak definiować architektury Radara.

Docelowo system powinien umożliwić:

```text
GitHub
GitLab
Bitbucket
Local repository
Other enterprise sources
        ↓
RepositorySnapshot
        ↓
Radar Core
```

Radar Core powinien analizować dane repozytorium, a nie „GitHuba”.

GitHub powinien być adapterem źródła.

v0.9 nie implementuje nowych źródeł.

---

# 4. Obecny zakres Radar Core

Przed rozpoczęciem v0.9 Radar posiada funkcjonalność rozwijaną przez wcześniejsze milestone'y.

## v0.1

Repository inventory.

Radar odpowiada na pytanie:

> What exists in this repository?

Obejmuje między innymi:

* Entity,
* Fact,
* Evidence,
* technology detection.

---

## v0.2

Configuration understanding.

Radar analizuje między innymi:

* CMake,
* Docker,
* Python,
* Node,
* CI runtime configuration.

---

## v0.3

Trust and context.

Dodano kontekst informacji:

* scope,
* source type,
* environment,
* confidence.

---

## v0.4

Repository map.

Radar rozpoznaje:

* directory roles,
* important files,
* entry points,
* repository structure,
* subprojects.

---

## v0.5

File dependency graph.

Radar analizuje deterministyczne zależności między plikami.

Obsługiwane są między innymi:

* Python imports,
* JavaScript/TypeScript relative imports,
* C/C++ local includes.

---

## v0.6

Component graph.

Radar grupuje pliki w logiczne komponenty.

---

## v0.7

Impact analysis.

Radar odpowiada na pytanie:

> What depends on X?

Obsługuje między innymi:

* direct dependents,
* transitive dependents,
* dependency path,
* distance,
* evidence.

---

## v0.8

Repository snapshots and deterministic diff.

Radar może porównywać dwa konkretne stany repozytorium.

Obsługuje:

* changed files,
* added files,
* removed files,
* changed facts,
* changed relationships,
* changed components,
* impact of changed elements.

---

## v0.8.x

Validation hardening.

Dodano:

* public repository validation corpus,
* smoke / scan / deep validation,
* pinned immutable SHAs,
* heavy repository workflow,
* GitHub source hardening,
* defensive parsing.

Obecny baseline:

```text
Backend tests: 93 passing
Validation harness tests: 11 passing
Validation corpus: 18 repositories
Compatibility: 18/18 scan successfully
```

Known heavy repositories:

```text
denoland/deno
llvm/llvm-project
```

wymagają większego timeoutu niż standardowe 180 sekund.

---

# 5. Problem do rozwiązania

Radar działa funkcjonalnie, ale struktura projektu rosła razem z kolejnymi milestone'ami.

Może to prowadzić do problemów takich jak:

* zbyt duże moduły,
* mieszanie orchestration z domain logic,
* source-specific logic znajdująca się za blisko core,
* testy zorganizowane historycznie zamiast funkcjonalnie,
* validation tooling traktowane jako luźne skrypty,
* developer wymagający znajomości wielu komend,
* brak jasnego CI contract,
* brak formalnego architecture documentation,
* brak prostego onboarding path.

Typowym przykładem wymagającym audytu jest:

```text
scanner.py
```

który wraz z rozwojem Radara zaczął pełnić wiele odpowiedzialności.

Nie oznacza to automatycznie, że należy go całkowicie rozbić.

Agent powinien najpierw zrozumieć jego rzeczywistą odpowiedzialność.

---

# 6. Target architecture

Docelowy przepływ systemu powinien być czytelny.

Conceptually:

```text
Source Adapter
      ↓
RepositorySnapshot
      ↓
Application / Orchestration Layer
      ↓
Radar Core
 ┌────┼─────────┬──────────┐
 ↓    ↓         ↓          ↓
Facts Graph Components   Diff
            ↓
          Impact
      ↓
API / future UX / future AI
```

Warstwy nie muszą posiadać dokładnie takich nazw katalogów.

Najważniejsza jest odpowiedzialność i kierunek zależności.

---

# 7. API layer

API powinno odpowiadać przede wszystkim za:

* request parsing,
* response serialization,
* HTTP error mapping,
* calling application services.

API nie powinno zawierać dużej części analizy repozytorium.

Endpoint typu:

```text
POST /scan
```

powinien przede wszystkim uruchamiać odpowiedni use case.

Podobnie:

```text
POST /impact
POST /diff
```

---

# 8. Application / orchestration layer

Application layer powinien odpowiadać za koordynację działań.

Przykładowo scan może logicznie wyglądać jak:

```text
load repository
      ↓
create snapshot
      ↓
extract facts
      ↓
build repository graph
      ↓
build component graph
      ↓
persist / return result
```

Ta warstwa może wiedzieć, że kilka subsystemów musi zostać uruchomionych.

Nie powinna jednak implementować parserów ani algorytmów graph analysis.

---

# 9. Radar Core

Radar Core powinien być możliwie niezależny od transportu i konkretnego źródła.

Core obejmuje logicznie:

* facts,
* evidence,
* repository analysis,
* dependency graph,
* component graph,
* impact,
* diff,
* snapshot semantics.

Core nie powinien potrzebować wiedzy o:

```text
GitHub REST API
FastAPI request
Jenkins
HTTP authentication
```

---

# 10. Source adapters

Source layer odpowiada za pobranie danych.

Przykładowo:

```text
GitHubSource
```

powinien odpowiadać za:

* repository metadata,
* ref resolution,
* commit SHA resolution,
* tree retrieval,
* file contents,
* GitHub-specific error mapping.

Dane powinny zostać przekazane dalej w source-neutral form.

Future sources mogą obejmować:

```text
GitLabSource
BitbucketSource
LocalSource
```

Nie implementujemy ich w v0.9.

---

# 11. Extractors

Extractors powinny być małe i deterministyczne.

Przykładowe obszary:

```text
configuration
python
javascript
cpp
docker
cmake
ci
```

Extractor:

* otrzymuje konkretne dane,
* zwraca facts/evidence,
* nie wykonuje network operations,
* nie powinien wiedzieć o API transport.

Nietypowe lub malformed dane nie powinny powodować crasha całego Radara.

Defensive parsing pozostaje wymaganiem.

---

# 12. Graph subsystem

Graph logic powinno być możliwe do zrozumienia niezależnie od source layer.

Powinny istnieć czytelne odpowiedzialności dla:

```text
repository dependency graph
component graph
impact analysis
```

Impact powinien nadal oznaczać dependency reachability.

Nie dodajemy risk scoring ani przewidywania:

> „to na pewno się zepsuje”.

---

# 13. Diff subsystem

Diff powinien nadal porównywać dwa immutable RepositorySnapshots.

Powinien zachować:

* file changes,
* semantic fact changes,
* relationship changes,
* component changes,
* impact reuse.

Nie dodajemy historii Git jako nowej funkcjonalności.

To zostanie rozważone po v0.9.

---

# 14. Persistence

Storage layer powinien być wyraźnie oddzielony od core semantics.

SQLite pozostaje obecnym persistence mechanism.

v0.9 nie migruje na:

```text
PostgreSQL
Redis
Neo4j
```

tylko dlatego, że mogłyby wyglądać bardziej produkcyjnie.

Storage abstractions powinny istnieć tylko tam, gdzie dają realną korzyść.

---

# 15. Validation subsystem

Validation corpus powinien być traktowany jak oddzielny subsystem projektu.

Obecnie zawiera:

* corpus repo definitions,
* pinned commit SHAs,
* runner,
* smoke mode,
* scan mode,
* deep mode,
* heavy repo handling,
* resume,
* tag filters,
* JSON reports.

Nie powinien wyglądać jak przypadkowe pliki wrzucone do `scripts/`.

Preferowany kierunek może wyglądać jak:

```text
validation/
├── corpus.json
├── runner.py
├── README.md
└── ...
```

Agent może zaproponować lepszą strukturę, jeśli wynika z obecnego kodu.

---

# 16. Developer Experience

Nowy developer nie powinien potrzebować znać wewnętrznych poleceń projektu.

Repo powinno posiadać prosty entry point dla typowych czynności.

Preferowane komendy:

```bash
make setup
make verify-env
make test
make check
make smoke
make run
```

---

# 17. make setup

Powinno przygotowywać lokalne środowisko developerskie.

Nie powinno wykonywać destrukcyjnych zmian w systemie.

---

# 18. make verify-env

Powinno szybko sprawdzać podstawowe wymagania.

Przykładowo:

```text
Python version
Dependencies
Virtual environment
Database path
Cache path
GitHub authentication
Required local tools
```

Output powinien być czytelny:

```text
Python          PASS
Dependencies    PASS
Database        PASS
Cache           PASS
GitHub auth     PASS
```

Brak GitHub tokena może być warningiem, jeśli dana operacja umożliwia anonymous GitHub access.

Token nie może zostać wypisany.

---

# 19. make test

Uruchamia testy projektu.

Powinien być stabilnym publicznym developer command niezależnie od wewnętrznej organizacji pytest.

---

# 20. make check

Powinien być standardowym developer gate przed pushem.

Conceptually:

```text
Environment sanity
      ↓
Static checks
      ↓
Backend tests
      ↓
Harness tests
      ↓
Smoke validation
```

Ma być wystarczająco szybki, żeby developer rzeczywiście z niego korzystał.

Nie powinien uruchamiać:

```text
LLVM
TensorFlow
Deno heavy validation
full deep corpus
```

---

# 21. make smoke

Uruchamia szybki representative compatibility test.

Obecny validation harness posiada smoke profile.

Należy wykorzystać istniejący mechanizm zamiast tworzyć drugi.

---

# 22. Test architecture

Testy powinny zostać przeanalizowane pod kątem organizacji.

Preferowane logiczne kategorie:

```text
unit
extractors
integration
api
architecture
fixtures
```

Nie trzeba automatycznie przenosić wszystkich testów.

Test organization należy zmieniać tylko wtedy, gdy poprawia:

* discoverability,
* ownership,
* clarity.

Historyczne nazwy testów milestone'owych mogą zostać zachowane lub stopniowo zmigrowane.

---

# 23. Architecture tests

Jeżeli podczas v0.9 powstaną jasne boundaries, można dodać testy zapobiegające ich późniejszemu łamaniu.

Przykład:

```text
Radar Core must not import GitHub source implementation.
```

Lub:

```text
Extractors must not depend on FastAPI.
```

Takie testy należy dodawać tylko dla stabilnych i świadomych granic.

---

# 24. CI philosophy

CI ma działać podobnie do profesjonalnego systemu produkcyjnego.

Developer lokalnie wykonuje szybkie testy.

CI ponownie weryfikuje kod niezależnie.

Ciężkie testy odbywają się oddzielnie.

---

# 25. Fast PR / push pipeline

Pipeline dla normalnych zmian powinien wyglądać konceptualnie:

```text
Environment Verification
        ↓
Static / syntax checks
        ↓
Backend tests
        ↓
Validation harness tests
        ↓
Smoke corpus
        ↓
PASS / FAIL
```

Pipeline nie powinien trwać godzinę.

---

# 26. Nightly pipeline

Nightly może być znacznie cięższy.

Conceptually:

```text
Backend regression suite
        ↓
Validation harness suite
        ↓
Full 18-repository scan corpus
        ↓
Representative deep corpus
        ↓
Heavy repositories
        ↓
Performance measurements
        ↓
Archive reports
```

Heavy validation może działać długo.

Jest to celowy tradeoff.

---

# 27. CI infrastructure separation

Jenkins nie musi żyć w głównym Radar repo.

Radar repo powinno definiować:

> WHAT must be tested.

Infrastructure może definiować:

> WHERE and HOW Jenkins executes it.

Możliwa przyszła struktura:

```text
radar
```

oraz:

```text
radar-infra
```

---

# 28. Radar CI contract

Radar repo może posiadać prosty katalog:

```text
ci/
```

z konfiguracją jobów.

Przykładowo:

```text
ci/jobs.yaml
```

lub:

```text
ci/jobs.json
```

może definiować logiczne zadania:

```text
verify-env
test
smoke
scan
deep
heavy
```

Nie należy budować własnego skomplikowanego pipeline language.

CI config powinien jedynie zapewnić stabilny kontrakt dla:

* Jenkins,
* future GitHub Actions,
* future other CI.

---

# 29. radar-infra

Jeżeli w przyszłości powstanie osobne repo infrastrukturalne, może zawierać:

```text
jenkins/
docker/
monitoring/
provisioning/
cache/
```

Może zarządzać:

* Jenkins controller,
* Jenkins agents,
* Docker environment,
* credentials,
* cache volumes,
* monitoring,
* backups.

Nie tworzymy osobnego repo tylko dla estetyki.

Powstaje dopiero wtedy, kiedy infrastruktura rzeczywiście jest implementowana.

---

# 30. Cache

Validation corpus korzysta z immutable pinned commit SHAs.

Przykład:

```text
repository = nodejs/node
commit = ecd365...
```

Dane dla tego samego commit SHA nie zmienią się.

Nie ma potrzeby pobierać ich ponownie przy każdym nightly.

---

# 31. Cache identity

Naturalny cache key:

```text
repository + commit_sha
```

Potencjalnie cache może przechowywać:

* metadata,
* repository tree,
* file contents,
* snapshot data.

---

# 32. Cache requirements

Cache:

* jest opcjonalny,
* nie zmienia semantyki analizy,
* hit i miss dają ten sam wynik,
* nie przechowuje credentiali,
* corrupted cache można usunąć/rebuild,
* nie może przeciekać do Radar Core,
* nie może powodować false data dla innego SHA.

Na początek filesystem cache jest wystarczający.

Nie implementujemy Redis/S3 cache tylko dlatego, że są popularne.

---

# 33. Performance tracking

Radar powinien zacząć zbierać podstawowy baseline wydajności.

Validation report może zapisywać:

```text
repository
commit SHA
file count
scan duration
fact count
relationship count
component count
status
```

Pozwoli to później wykryć regresje.

Przykład:

```text
Node v0.9
52k files
150 s
```

po zmianie:

```text
Node v0.10
52k files
390 s
```

To powinno być widoczne jako potencjalna performance regression.

Nie implementujemy jeszcze automatycznego hard performance gate.

---

# 34. Dokumentacja

Repo ma być self-explanatory.

Dokumentacja nie może istnieć tylko dlatego, że milestone wymaga kolejnego MD.

Powinna odpowiadać na realne pytania developera.

---

# 35. README

README ma być wejściem do projektu.

Powinno wyjaśniać:

```text
What is Radar?
Why does it exist?
How does it work?
How do I run it?
How do I test it?
Where is the architecture documentation?
```

README nie powinno być pełną dokumentacją techniczną.

---

# 36. architecture.md

Powinno pokazywać aktualną architekturę.

Minimum:

```text
Sources
  ↓
RepositorySnapshot
  ↓
Application
  ↓
Radar Core
  ↓
Facts / Graph / Components / Impact / Diff
```

Powinno również opisywać dependency boundaries.

---

# 37. development.md

Powinno opisywać:

* setup,
* environment,
* make commands,
* local API,
* test workflow,
* debugging,
* common development operations.

---

# 38. testing.md

Powinno wyjaśniać różnicę pomiędzy:

```text
unit tests
integration tests
API tests
validation corpus
smoke
scan
deep
heavy
```

---

# 39. ci.md

Powinno opisywać:

```text
local verification
PR/push pipeline
nightly pipeline
heavy validation
reports
cache
external Jenkins architecture
```

---

# 40. Architecture Decision Records

Warto stworzyć:

```text
docs/decisions/
```

dla ważnych decyzji.

Przykładowe ADR:

```text
0001-evidence-first.md
0002-unknown-over-guessing.md
0003-deterministic-core-before-ai.md
0004-source-neutral-core.md
0005-validation-corpus.md
```

ADR mają tłumaczyć:

> WHY

a nie powtarzać implementację.

---

# 41. Secrets

Repo nie może zawierać:

* GitHub tokenów,
* Jenkins credentials,
* passwords,
* environment secrets.

CI powinno otrzymywać je poprzez environment / credentials store.

Validation logs nie mogą wypisywać tokenów.

---

# 42. Dependency policy

Nie należy dodawać dużej liczby bibliotek tylko po to, żeby zrobić refactor.

Preferowane są:

* standard library,
* obecne dependencies,
* proste rozwiązania.

Każda nowa dependency powinna mieć realny powód.

---

# 43. Scripts and tools

Utility scripts powinny być łatwe do znalezienia.

Jeżeli coś jest częścią subsystemu validation, powinno znajdować się tam.

`tools/` lub `scripts/` powinny zawierać rzeczy, które rzeczywiście są narzędziami pomocniczymi.

Nie powinny być miejscem, do którego trafia wszystko, czego nie wiadomo gdzie umieścić.

---

# 44. Naming

Nazwy modułów i katalogów powinny opisywać odpowiedzialność.

Preferujemy:

```text
validation
sources
extractors
storage
graph
impact
diff
```

zamiast nazw zależnych od wewnętrznego slangu.

Nowy developer powinien móc zgadnąć przeznaczenie katalogu bez dokumentacji.

---

# 45. Refactor strategy

v0.9 nie może być giant rewrite.

Agent powinien działać krokami.

Przykładowy workflow:

```text
1. Understand current architecture
2. Run baseline tests
3. Propose boundaries
4. Move one responsibility
5. Run focused tests
6. Continue
7. Run complete regression
8. Run validation corpus
```

Duża liczba zmian bez testowania pośredniego jest nieakceptowalna.

---

# 46. Zachowanie Git

Agent:

* nie wykonuje commit,
* nie wykonuje push,
* nie tworzy tagów,
* nie robi rebase,
* nie resetuje historii.

Git operations pozostają po stronie developera.

---

# 47. Out of scope v0.9

v0.9 NIE implementuje:

* Git History / Change Context,
* Jira,
* Confluence,
* Jenkins jako Radar data source,
* GitLab,
* Bitbucket,
* AI,
* Ask Radar,
* ownership inference,
* company-wide graph,
* UI,
* authentication system,
* billing,
* customer management.

To będą przyszłe milestone'y.

---

# 48. Acceptance tests

Po zakończeniu refactoru należy wykonać:

## Backend tests

Cały regression suite.

Baseline:

```text
93 passing
```

Liczba może wzrosnąć.

Nie może spaść dlatego, że testy zostały usunięte.

---

## Validation harness tests

Baseline:

```text
11 passing
```

---

## Smoke

Smoke profile musi przejść.

---

## Full compatibility scan

Wszystkie 18 pinned repo muszą przejść scan.

Expected:

```text
18/18 compatibility PASS
```

---

## Heavy validation

Deno oraz LLVM muszą nadal przejść przy odpowiednim heavy timeout/profile.

---

## Git diff

```bash
git diff --check
```

musi przejść.

---

# 49. Regression rule

Jeżeli refactor powoduje zmianę wyników dla pinned corpus repo:

nie należy automatycznie aktualizować expected behavior.

Najpierw trzeba ustalić:

> czy była to zamierzona poprawa czy regresja.

v0.9 nie jest milestone'em do zmiany semantyki analizy.

---

# 50. Definition of Done

Radar v0.9 jest gotowy, gdy:

* architecture boundaries są jasne,
* core nie jest logicznie zależny od GitHuba,
* duże orchestration responsibilities są uporządkowane,
* validation jest czytelnym subsystemem,
* developer posiada prosty local workflow,
* CI contract istnieje,
* nightly strategy jest udokumentowana,
* heavy validation jest oddzielona od fast checks,
* cache boundary jest zaimplementowane lub sensownie zaprojektowane,
* docs odpowiadają rzeczywistemu kodowi,
* testy przechodzą,
* corpus przechodzi,
* zachowanie v0.8.x jest zachowane.

---

# 51. Final quality bar

Po zakończeniu milestone'u dajemy repo senior developerowi, który nigdy wcześniej nie widział Radara.

Powinien po krótkim czasie umieć powiedzieć:

> Wiem gdzie jest core.

> Wiem gdzie jest GitHub adapter.

> Wiem jak przechodzi RepositorySnapshot.

> Wiem gdzie budowany jest graph.

> Wiem gdzie działa impact.

> Wiem gdzie działa diff.

> Wiem jak uruchomić testy.

> Wiem co odpalić przed pushem.

> Wiem co odpala CI.

> Wiem gdzie dodałbym nowy extractor.

> Wiem gdzie kiedyś dodać GitLab.

> Nie muszę pytać autora projektu jak ten system działa.

Jeżeli zamiast tego reakcja brzmi:

> „Nie wiem czemu to jest tutaj, ale najwyraźniej działa.”

to v0.9 nie jest skończone.

---

# 52. Philosophy

Radar ma być rozwijany przez wiele kolejnych milestone'ów.

Koszt złej architektury rośnie wraz z każdą nową funkcją.

v0.9 celowo zatrzymuje rozwój feature'ów, aby stworzyć solidny engineering foundation przed dalszym rozwojem.

Nie optymalizujemy repo pod:

> „AI wygenerowało kod i testy przechodzą.”

Optymalizujemy pod:

> „Profesjonalny zespół może rozwijać ten system przez lata.”
