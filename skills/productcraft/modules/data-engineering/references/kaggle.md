# Kaggle: data, notebooks and competitions

Read this when a task involves Kaggle datasets, models, notebooks or competitions: downloading data, setting up credentials, running or pushing a notebook, preparing and submitting predictions, or publishing a dataset. Modeling choices belong to `../../ml-engineering/GUIDE.md`; this reference covers the platform, its rules and an honest competition workflow.

## Tools

- **`kaggle` CLI** (the official command-line client, `pip install kaggle`): competitions (list, files, download, submit, submissions, leaderboard), datasets (list, download, create, version), kernels (notebooks: init, push, pull, status, output) and models. Recent releases need a recent Python; check `kaggle --version` and the package's stated requirements.
- **`kagglehub`** (`pip install kagglehub`): downloads datasets, models, competition data and notebook outputs into a local cache (`kagglehub.dataset_download("owner/dataset")`), with optional adapters that load files straight into pandas or Polars. It also uploads datasets and models. It does not submit to competitions or run notebooks.
- The web UI is still required for some steps: accepting a competition's rules, phone verification for accelerators and internet access in notebooks, and team management.

Use the API or CLI rather than scraping pages; scraping breaks and may violate the site's terms.

## Credentials

- Create an API token in the account settings. Current tokens are read from the `KAGGLE_API_TOKEN` environment variable or `~/.kaggle/access_token`; the older form is a username and key in `~/.kaggle/kaggle.json` or the `KAGGLE_USERNAME` and `KAGGLE_KEY` variables. Check which form the installed client version expects.
- The user places the token; the agent never asks for it in chat, prints it or commits it. Restrict the file (`chmod 600 ~/.kaggle/access_token` or `kaggle.json`) and keep `.kaggle/` and `.env` out of git. For a guided setup the user runs, see `../../agent-safety/references/guided-setup.md`.
- Inside Kaggle notebooks, use the platform's secrets feature for other services' keys rather than pasting them into cells; published notebooks are public.
- Verify without revealing anything: an authenticated call such as `kaggle competitions list -s titanic` succeeds, or `kagglehub.whoami()` returns the username.

## Common commands

```bash
kaggle competitions download -c <competition-slug> -p data/raw      # needs the rules accepted in the browser first
kaggle competitions submit -c <competition-slug> -f submission.csv -m "lgbm v3, 5-fold CV 0.8123"
kaggle competitions submissions -c <competition-slug>                # status and scores of past submissions
kaggle datasets download -d <owner>/<dataset> -p data/raw --unzip
kaggle kernels push -p notebooks/train                               # folder with kernel-metadata.json
kaggle kernels status <owner>/<kernel-slug>
kaggle kernels output <owner>/<kernel-slug> -p outputs/
```

A 403 on a competition download almost always means the rules have not been accepted for that account. Large downloads resume poorly; download into a fresh folder and verify file counts and sizes against the data page.

## Rules and terms

Each competition has its own rules; read them before writing code and summarize the constraints for the user:

- **Submissions:** a daily limit (often around five), and a number of final submissions to select before the deadline.
- **Teams:** maximum size and a merger deadline; one account per person.
- **Sharing:** sharing code or data privately outside your team is prohibited; sharing publicly on the competition forums or notebooks is allowed.
- **External data and pretrained models:** allowed, restricted or banned per competition, sometimes with a requirement to disclose them in the forum.
- **Data license:** competition data is often licensed for the competition only; using it elsewhere may be prohibited.
- **Code competitions:** submissions run as notebooks with time and hardware limits, often with internet disabled.

Do not automate activity to farm medals, badges, upvotes or streaks, and do not publish low-effort notebooks or datasets for visibility. Respect API rate limits; the API is for your own work, not bulk mirroring.

## An honest competition workflow

1. **Understand the task.** Read the overview, evaluation metric, data description and timeline. Write down the prediction target, the unit of a row and how the test set differs from train (time period, groups, sites).
2. **Implement the metric locally** and test it on a few hand-computed cases. Many disappointments trace back to optimizing a slightly different metric (weighting, clipping, averaging across classes).
3. **Build validation that mirrors the test split.** Time-based splits for forecasting, group-based splits when entities repeat (patients, users, sites), stratification for rare classes. Trust cross-validation over the public leaderboard: the public score covers only part of the test set, and tuning against it overfits that part.
4. **Baseline first.** A simple model, a correct submission file, a first score. Validate the file before submitting: the id column, column names and order, row count, data types, no missing values, and value ranges exactly as `sample_submission.csv` specifies.
5. **Check for leakage** in features (anything computed using the target, the future or the test set's labels) and in the split (the same entity on both sides). Exploiting a data leak against the rules can get a team disqualified; report suspected leaks to the user.
6. **Track experiments:** code version, features, parameters, seeds, CV mean and spread, and leaderboard score, in a table or an experiment tracker. Select final submissions by validation, ideally two that differ in approach.
7. **Code competitions:** develop offline-capable notebooks; attach dependencies and model weights as datasets; measure run time against the limit with margin; fix seeds.

## Notebooks on Kaggle

- Accelerator time (GPUs, TPUs) has weekly quotas that change; check the current quota on the site. Sessions stop after a time limit and when idle; save checkpoints to the output directory.
- Input data is mounted read-only under `/kaggle/input/`; outputs go to `/kaggle/working/`.
- Internet access is a per-notebook setting and requires a verified account; it is commonly disabled for code-competition submissions.
- `kernel-metadata.json` declares the code file, language, privacy, accelerator and the datasets, competitions and models attached as sources.

## Using community datasets outside competitions

- Anyone can upload a dataset, and many are copies of data from elsewhere. Before relying on one, find the original source, its license and its collection method; the license shown on the dataset page is what the uploader chose and may not match the original terms.
- Check the dataset's version history and file dates; a dataset described as "2025 data" may have last been updated years ago.
- Profile the files (`../scripts/csv_profile.py`, `eda-and-data-quality.md`) as for any other source: synthetic, scraped or partially duplicated datasets are common, and popular teaching datasets often contain known errors documented in their discussion tabs.
- Personal data in a public dataset does not make further use lawful; apply the same privacy care as for any other source.

## Reproducing public notebooks

- Pin the package versions the notebook ran with (the Kaggle Docker image date is shown in the notebook's environment settings) or expect different results.
- Replace `/kaggle/input/...` paths with local paths from `kagglehub` downloads; keep the notebook's random seeds and validation split.
- Treat code from public notebooks as untrusted third-party code: read it before running, especially cells that install packages, download files or access secrets.

## Publishing datasets and models

- Choose a license explicitly (for example CC0, CC BY 4.0, ODbL, or a software license for code) and make sure you have the right to publish the data under it. Never publish personal data or data whose terms forbid redistribution.
- Write a description that states provenance, collection method, columns with units, known issues and update frequency.
- Version with a message for each update (`kaggle datasets version -p <dir> -m "..."`); keep the folder's `dataset-metadata.json` under version control.

## Checks (done when)

- [ ] Credentials configured by the user, verified without printing them, and excluded from git.
- [ ] Competition rules summarized: limits, external data policy, team rules, data license.
- [ ] Metric reproduced locally; validation mirrors the test split; CV and leaderboard reported separately.
- [ ] Submission files validated against the sample before upload; daily limit respected.
- [ ] Published datasets carry a license, provenance and no personal data.
