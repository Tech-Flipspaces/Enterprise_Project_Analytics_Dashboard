This is the standard workflow for team development! You are effectively onboarding a new developer.

To get their machine perfectly synced with your database configuration (Metrics, User Groups, Departments, etc.), they will use Django's built-in `loaddata` command.

Here is the exact step-by-step guide you can send to your colleague to get them up and running in 5 minutes.

### **Prerequisite: Share the Code & File**

1. Ensure they have cloned your GitHub repository to their machine.
2. Send them the `db_backup.json` file securely (via Slack, Teams, or email) and tell them to place it inside the `backend` folder of the cloned repository. *(Note: If you pushed this file to a private GitHub repo, they will already have it).*

---

### **The Setup Guide for Your Colleague**

Tell your colleague to open their VS Code terminal, navigate to the project folder, and run these commands:

#### **Step 1: Setup the Environment**

They need to create a virtual environment and install the required Python packages.

```bash
# 1. Create a virtual environment
python -m venv env

# 2. Activate it
# For Windows:
env\Scripts\activate
# For Mac/Linux:
source env/bin/activate

# 3. Install the dependencies
pip install -r requirements.txt

```

#### **Step 2: Prepare the Local Database**

They need to create their own empty, local SQLite database matching your structure.

```bash
# 1. Go into the backend folder where manage.py lives
cd backend

# 2. Build the database structure
python manage.py migrate

```

#### **Step 3: Load the Configuration Data (The Magic Step)**

Now, they will inject all your Admin configurations (Metrics, User Groups, Rules) into their empty database using your backup file.

```bash
# Run the loaddata command targeting the backup file
python manage.py loaddata db_backup.json

```

*If successful, the terminal will say something like: `Installed 145 object(s) from 1 fixture(s)`.*

#### **Step 4: Create a Local Admin Account**

Even though they loaded the data, they might need their own admin login for their local machine.

```bash
python manage.py createsuperuser
# Follow the prompts to set a username and password

```

#### **Step 5: Run the Server**

They are now fully synced! They can start the server.

```bash
python manage.py runserver

```

### **A Quick Pro-Tip on Co-Working:**

Whenever you (or your colleague) add new Metrics, Departments, or User Groups in the Admin Panel, that data only exists on *your* machine.

To share those new changes with each other in the future:

1. **You:** Run `python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 -o db_backup.json` and send them the new file.
2. **Them:** Save the new file and run `python manage.py loaddata db_backup.json` to overwrite their local database with your new rules.

This keeps you both perfectly in sync without messing up the actual code!