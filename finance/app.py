import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

import datetime
import re
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]

    shares_buy = db.execute(
        "SELECT symbol, name, SUM(shares) AS shares, price FROM buy_shares WHERE user_id = ? GROUP BY symbol", user_id)
    cash_list = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_list[0]["cash"]
    total = cash
    for i in shares_buy:
        total += i["price"] * i["shares"]
    return render_template("index.html", table=shares_buy, cash=usd(cash), total=usd(total), usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        element = lookup(symbol)

        if not symbol:
            return apology("Enter a symbol!")
        elif not element:
            return apology("Incorrectly entered symbol!")

        shares = request.form.get("shares")
        if not shares.isdigit():
            return apology("Enter number shares!")
        shares = int(shares)
        if shares < 0:
            return apology("Enter number shares!")

        number_shares = shares * element["price"]
        user_id = session["user_id"]
        users_cash_list = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = users_cash_list[0]["cash"]

        if user_cash < number_shares:
            return apology("Not enough money!")
        else:
            cash_new = user_cash - number_shares
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_new, user_id)
            date = datetime.datetime.now()

            db.execute("INSERT INTO buy_shares (user_id, symbol, name, shares, price, type, time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       user_id, element["symbol"], element["name"], shares, element["price"], "buy", date)

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    buy_shares = db.execute("SELECT symbol, name, type, shares, price, time FROM buy_shares WHERE user_id = ?", user_id)
    return render_template("history.html", table=buy_shares, usd=usd)


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
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Enter a symbol!")
        element = lookup(symbol)
        if not element:
            return apology("Incorrectly entered symbol!")
        element_price = usd(element["price"])
        return render_template("quoted.html", element=element, element_price=element_price)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Enter username!")
        elif not password or not confirmation:
            return apology("Enter password!")

        if password != confirmation:
            return apology("Confirm password!")

        if len(password) < 9:
            return apology("Password must not be longer than 9 characters")
        elif not re.search("[A-Z]", password):
            return apology("Password must contain at least one uppercase letter")
        elif not re.search("[0-9]", password):
            return apology("Password must contain at least one digit")
        elif not re.search("[!@*$%?_-~]",password):
            return apology("Password must contain at least one special charaster(! @ * $ % ? _ - ~)")


        all_names = [x["username"] for x in db.execute("SELECT username FROM users")]
        if username in all_names:
            return apology("Username has already registered!")

        hash_password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not shares.isdigit():
            return apology("Enter number shares!")
        shares = int(shares)
        if shares < 0:
            return apology("Enter number shares!")

        price = lookup(symbol)["price"]
        name = lookup(symbol)["name"]
        price_shares = shares * price

        shares_now = db.execute("SELECT shares FROM buy_shares WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)
        shares_n = shares_now[0]["shares"]
        if shares_n < shares:
            return apology("You don't have enough shares!")

        cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash_db[0]["cash"]
        after_sell = cash + price_shares

        date = datetime.datetime.now()
        db.execute("UPDATE users SET cash = ? WHERE id = ?", after_sell, user_id)
        db.execute("INSERT INTO buy_shares (user_id, symbol, name, shares, price, type, time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   user_id, symbol, name, -shares, price, "sell", date)
        return redirect("/")

    else:
        symbols = db.execute("SELECT symbol FROM buy_shares WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)

