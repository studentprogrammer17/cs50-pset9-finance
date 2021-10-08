import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "GET":
        holding = []
        all_cash = 0
        rows = db.execute("SELECT symbol,SUM(shares) as Shares FROM users_actions WHERE user_id = ? GROUP BY symbol",session["user_id"])
        for i in rows:
            look_up = lookup(i["symbol"])
            holding.append({"symbol": look_up["symbol"],"name": look_up["name"],"shares": i["Shares"],"price": usd(look_up["price"]),"hold": usd(i["Shares"] * look_up["price"])})
            all_cash += i["Shares"] * look_up["price"]

        money = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = money[0]["cash"]
        all_cash += cash

        return render_template("index.html",holding = holding,money = usd(cash),all_cash = usd(all_cash))

    else:
        money = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = money[0]["cash"]
        add_cash = int(request.form.get("add_money"))
        added_cash = add_cash + int(cash)
        db.execute("UPDATE users SET cash = ? WHERE id = ?",added_cash,session["user_id"])

        return redirect("/")






@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        look_up = lookup(symbol)
        if look_up == None:
            return apology("This symbol doesn't exist")
        rows = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = rows[0]["cash"]
        cash_after_buy = cash - (shares * look_up["price"])
        if cash_after_buy < 0:
            return apology("Not enough money")
        else:
            company_name = look_up['name']
            db.execute("UPDATE users SET cash = ? WHERE id = ?",cash_after_buy,session["user_id"])
            db.execute("INSERT INTO users_actions (user_id,symbol,shares,price,Action) VALUES (?,?,?,?,?)",session["user_id"],look_up["symbol"],shares,look_up["price"], "Bought")
            if shares == 1:
                flash(f"{shares} shares of {company_name} is bought")
            else:
                flash(f"{shares} shares of {company_name} are bought")
            return redirect("/")
    else:
        money = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = money[0]["cash"]
        return render_template("buy.html", money = usd(cash))


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT symbol,shares,price,time,Action FROM users_actions  WHERE user_id = ? ORDER BY time DESC",session["user_id"])
    return render_template("history.html",history = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        look_up = lookup(symbol)
        if look_up == None:
            return apology("This symbol doesn't exist")
        look_up = {"name": look_up["name"],"price": usd(look_up["price"]),"symbol": look_up["symbol"]}
        return render_template("quoted.html", look_up = look_up)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        if db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")):
            return apology("This username has already used", 403)

        db.execute("INSERT INTO users (username,hash) VALUES (?,?)",request.form.get("username"),generate_password_hash(request.form.get("password")))
        return render_template("login.html")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    symbols = db.execute("SELECT symbol FROM users_actions WHERE user_id = ? GROUP BY symbol",session["user_id"])

    if request.method == "POST":
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        look_up = lookup(symbol)

        rows = db.execute("SELECT symbol,SUM(shares) as Shares FROM users_actions WHERE user_id = ? GROUP BY symbol",session["user_id"])

        for i in rows:
            if i["symbol"] == symbol:
                if shares > i["Shares"]:
                    return apology("You don't have enough shares of this stock to sell")


        rows = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        cash = rows[0]["cash"]
        cash_after_buy = cash + (shares * look_up["price"])

        db.execute("UPDATE users SET cash = ? WHERE id = ?",cash_after_buy,session["user_id"])
        sold_stock = 0
        sold_stock -= shares


        db.execute("INSERT INTO users_actions (user_id,symbol,shares,price,Action) VALUES (?,?,?,?,?)",session["user_id"],look_up["symbol"],sold_stock,look_up["price"],"Sold")

        company_name = look_up['name']
        if shares == 1:
            flash(f"{shares} shares of {company_name} is sold")
        else:
            flash(f"{shares} shares of {company_name} are sold")

        return redirect("/")
    else:
        return render_template("sell.html",symbols = symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
