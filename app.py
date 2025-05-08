from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='devtrivedi',
        database='Newark IT store',
        port=3307
    )

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT COUNT(*) AS cnt FROM Customer;')
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('index.html', customer_count=result['cnt'])

# — Customer CRUD —

@app.route('/customers')
def list_customers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT CID, FName, LName, Email FROM Customer;')
    customers = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('customers.html', customers=customers)


@app.route('/customers/new', methods=['GET', 'POST'])
def new_customer():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # 1) figure out the next CID
        cur.execute('SELECT IFNULL(MAX(CID), 0) + 1 AS nextcid FROM Customer;')
        nextcid = cur.fetchone()['nextcid']

        # 2) pull in all form fields
        fname   = request.form['fname']
        lname   = request.form['lname']
        email   = request.form['email']
        phone   = request.form['phone']
        status  = request.form['status']

        # ─── auto-generate SAName ─────────────────────────────────────────
        saname = f"home_{nextcid}"

        # 3) pull in your address pieces as before
        street    = request.form['street']
        number    = request.form['number']
        city      = request.form['city']
        zip_code  = request.form['zip']
        state     = request.form['state']
        country   = request.form['country']
        recipient = request.form['recipient']

        # 4) assemble the Customer.Address
        cust_address = f"{number} {street}, {city}, {state} {zip_code}"

        # 5) insert into Customer
        cur.execute(
          '''
           INSERT INTO Customer
             (CID, FName, LName, Email, Address, Phone, Status)
           VALUES
             (%s, %s, %s, %s, %s, %s, %s);
          ''',
          (nextcid, fname, lname, email, cust_address, phone, status)
        )

        # 6) insert into Shipping_Address, using our generated saname
        cur.execute(
          '''
           INSERT INTO Shipping_Address
             (CID, SAName, Street, SNumber, City, Zip, State, Country, RecepientName)
           VALUES
             (%s, %s, %s, %s, %s, %s, %s, %s, %s);
          ''',
          (nextcid, saname, street, number, city, zip_code, state, country, recipient)
        )

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_customers'))

    # GET → just render the blank form
    cur.close()
    conn.close()
    return render_template('new_customer.html')


@app.route('/customers/<int:cid>/edit', methods=['GET','POST'])
def edit_customer(cid):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # pull exactly the same names you used in the form:
        fname     = request.form['fname']
        lname     = request.form['lname']
        email     = request.form['email']
        phone     = request.form['phone']
        status    = request.form['status']

        # shipping‐address fields:
        sa_name   = request.form['sa_name']
        street    = request.form['street']
        number    = request.form['number']
        city      = request.form['city']
        zip_code  = request.form['zip']
        state     = request.form['state']
        country   = request.form['country']
        recipient = request.form['recipient']

        # 1) Update customer table
        cur.execute('''
            UPDATE Customer
            SET FName=%s, LName=%s, Email=%s, Phone=%s, Status=%s
            WHERE CID=%s
        ''', (fname, lname, email, phone, status, cid))

        # 2) Update the “Home” shipping address for that customer
        cur.execute('''
            UPDATE Shipping_Address
            SET SAName=%s,
                Street=%s,
                SNumber=%s,
                City=%s,
                Zip=%s,
                State=%s,
                Country=%s,
                RecepientName=%s
            WHERE CID=%s
              AND SAName = 'Home'
        ''', (sa_name, street, number, city, zip_code, state, country, recipient, cid))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_customers'))

    # — GET: load existing data to pre‐fill —
    cur.execute('SELECT * FROM Customer WHERE CID=%s', (cid,))
    customer = cur.fetchone()

    # load their “Home” address row
    cur.execute('''
      SELECT *
      FROM Shipping_Address
      WHERE CID=%s AND SAName = 'Home'
    ''', (cid,))
    addr = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
      'edit_customer.html',
      customer=customer,
      addr=addr
    )


@app.route('/customers/<int:cid>/delete', methods=['POST'])
def delete_customer(cid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM Customer WHERE CID=%s', (cid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('list_customers'))


# — Credit Card CRUD —
@app.route('/cards')
def list_cards():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    # pull in the customer name, if any
    cur.execute("""
      SELECT 
        CC.CCNumber, CC.SecNumber, CC.OwnerName, CC.CCType,
        CC.BillingAddress, CC.ExpDate, CC.StoredCardCID,
        CONCAT(C.FName, ' ', C.LName) AS CustomerName
      FROM Credit_Card CC
      LEFT JOIN Customer C
        ON CC.StoredCardCID = C.CID
      ORDER BY CC.ExpDate, CC.OwnerName
    """)
    cards = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('cards.html', cards=cards)


@app.route('/cards/new', methods=['GET','POST'])
def new_card():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # grab all the form fields
        ccnumber   = request.form['ccnumber']
        secnumber  = request.form['secnumber']
        ownername  = request.form['ownername']
        cctype     = request.form['cctype']
        billing    = request.form['billingaddr']
        expdate    = request.form['expdate']
        storedcid  = request.form.get('storedcid') or None

        # insert the new card, including the optional StoredCardCID
        cur.execute(
          """
          INSERT INTO Credit_Card
            (CCNumber, SecNumber, OwnerName, CCType, BillingAddress, ExpDate, StoredCardCID)
          VALUES (%s,%s,%s,%s,%s,%s,%s)
          """,
          (ccnumber, secnumber, ownername, cctype, billing, expdate, storedcid)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_cards'))

    # — on GET, load all customers into a dropdown —
    cur.execute("""
      SELECT CID, CONCAT(FName,' ',LName) AS fullname
      FROM Customer
      ORDER BY LName, FName
    """)
    customers = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('new_card.html', customers=customers)


@app.route('/cards/<ccnumber>/edit', methods=['GET','POST'])
def edit_card(ccnumber):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # pull exactly the names you’ll use in the form
        sec       = request.form['secnumber']
        owner     = request.form['ownername']
        cctype    = request.form['cctype']
        billing   = request.form['billingaddr']
        expdate   = request.form['expdate']
        # may be blank → None
        stored_cid = request.form.get('cid') or None

        # update the card
        cur.execute('''
            UPDATE Credit_Card
            SET SecNumber     = %s,
                OwnerName     = %s,
                CCType        = %s,
                BillingAddress= %s,
                ExpDate       = %s,
                StoredCardCID = %s
            WHERE CCNumber = %s
        ''', (sec, owner, cctype, billing, expdate, stored_cid, ccnumber))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_cards'))

    # — GET: load current card + list of customers for the dropdown —
    cur.execute('SELECT * FROM Credit_Card WHERE CCNumber=%s', (ccnumber,))
    card = cur.fetchone()

    cur.execute('SELECT CID, FName, LName FROM Customer ORDER BY CID')
    customers = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
      'edit_card.html',
      card=card,
      customers=customers
    )


@app.route('/cards/<ccnumber>/delete', methods=['POST'])
def delete_card(ccnumber):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM Credit_Card WHERE CCNumber=%s', (ccnumber,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('list_cards'))


# — Address CRUD —

@app.route('/addresses')
def list_addresses():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('SELECT * FROM Shipping_Address;')
    addresses = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('addresses.html', addresses=addresses)

@app.route('/addresses/new', methods=['GET','POST'])
def new_address():
    if request.method == 'POST':
        vals = [
            request.form['cid'],
            request.form['saname'],
            request.form['street'],
            request.form['snumber'],
            request.form['city'],
            request.form['zip'],
            request.form['state'],
            request.form['country'],
            request.form['recipient']
        ]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO Shipping_Address '
            '(CID,SAName,Street,SNumber,City,Zip,State,Country,RecepientName) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            vals
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_addresses'))
    return render_template('new_address.html')

@app.route('/addresses/<int:cid>/<saname>/edit', methods=['GET','POST'])
def edit_address(cid, saname):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        vals = [
            request.form['street'],
            request.form['snumber'],
            request.form['city'],
            request.form['zip'],
            request.form['state'],
            request.form['country'],
            request.form['recipient'],
            cid,
            saname
        ]
        cur.execute(
            'UPDATE Shipping_Address '
            'SET Street=%s,SNumber=%s,City=%s,Zip=%s,State=%s,Country=%s,RecepientName=%s '
            'WHERE CID=%s AND SAName=%s',
            vals
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_addresses'))

    cur.execute(
        'SELECT * FROM Shipping_Address WHERE CID=%s AND SAName=%s',
        (cid, saname)
    )
    address = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('edit_address.html', address=address)

@app.route('/addresses/<int:cid>/<saname>/delete', methods=['POST'])
def delete_address(cid, saname):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'DELETE FROM Shipping_Address WHERE CID=%s AND SAName=%s',
        (cid, saname)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('list_addresses'))


# 1) LIST ALL BASKETS
@app.route('/baskets')
def list_baskets():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute('''
      SELECT B.BID, B.CID, C.FName, C.LName,
             COALESCE(SUM(AI.Quantity * AI.PriceSold),0) AS Total
      FROM Basket B
      JOIN Customer C ON B.CID=C.CID
      LEFT JOIN Appears_In AI ON B.BID=AI.BID
      GROUP BY B.BID
      ORDER BY B.BID
    ''')
    baskets = cur.fetchall()
    cur.close(); conn.close()
    return render_template('baskets.html', baskets=baskets)

# 2) CREATE A NEW BASKET
@app.route('/baskets/new', methods=['GET', 'POST'])
def new_basket():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # pull the customer ID from the form
        cid = request.form['cid']

        # compute the next basket ID (or start at 5001 if none)
        cur.execute('SELECT MAX(BID) AS max_bid FROM Basket;')
        row = cur.fetchone()
        next_bid = (row['max_bid'] or 5000) + 1

        # insert the new basket
        cur.execute(
            'INSERT INTO Basket (BID, CID) VALUES (%s, %s);',
            (next_bid, cid)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_baskets'))

    # — GET: load all customers into the dropdown —
    cur.execute('SELECT CID, FName, LName FROM Customer ORDER BY FName, LName;')
    customers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('new_basket.html', customers=customers)

# 3) DELETE A BASKET (and its items via FK cascade)
@app.route('/baskets/<int:bid>/delete', methods=['POST'])
def delete_basket(bid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM Basket WHERE BID=%s', (bid,))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('list_baskets'))

# 4) VIEW / ADD / TOTAL for ONE BASKET
@app.route('/baskets/<int:bid>')
def view_basket(bid):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # basket + customer + status
    cur.execute('''
      SELECT B.BID, C.CID, C.FName, C.LName, C.Status
      FROM Basket B
      JOIN Customer C ON B.CID=C.CID
      WHERE B.BID=%s
    ''', (bid,))
    basket = cur.fetchone()

    # existing items
    cur.execute('''
      SELECT AI.PID, P.PName, AI.Quantity, AI.PriceSold
      FROM Appears_In AI
      JOIN Product P ON AI.PID=P.PID
      WHERE AI.BID=%s
    ''', (bid,))
    items = cur.fetchall()

    # compute running total
    total = sum(it['Quantity'] * float(it['PriceSold']) for it in items)

    # products for “add” dropdown
    cur.execute('SELECT PID, PName FROM Product ORDER BY PName')
    products = cur.fetchall()

    cur.close(); conn.close()
    return render_template('basket_detail.html',
                           basket=basket,
                           items=items,
                           total=total,
                           products=products)

# 5) ADD ITEM TO BASKET
@app.route('/baskets/<int:bid>/items/add', methods=['POST'])
def add_basket_item(bid):
    pid      = request.form['pid']
    qty      = int(request.form['quantity'])
    conn     = get_db_connection()
    cur      = conn.cursor(dictionary=True)

    # customer status
    cur.execute('''
      SELECT C.Status
      FROM Basket B JOIN Customer C ON B.CID=C.CID
      WHERE B.BID=%s
    ''', (bid,))
    status = cur.fetchone()['Status']

    # determine PriceSold
    price = None
    if status in ('gold','platinum'):
        cur.execute('SELECT OfferPrice FROM Offer_Product WHERE PID=%s', (pid,))
        row = cur.fetchone()
        if row: price = row['OfferPrice']
    if price is None:
        cur.execute('SELECT PPrice FROM Product WHERE PID=%s', (pid,))
        price = cur.fetchone()['PPrice']

    # insert or bump
    cur.execute('''
      INSERT INTO Appears_In (BID,PID,Quantity,PriceSold)
      VALUES (%s,%s,%s,%s)
      ON DUPLICATE KEY UPDATE
        Quantity = Quantity + VALUES(Quantity)
    ''', (bid, pid, qty, price))

    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('view_basket', bid=bid))

# 6) EDIT AN ITEM’S QUANTITY
@app.route('/baskets/<int:bid>/items/<int:pid>/edit', methods=['GET','POST'])
def edit_basket_item(bid, pid):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    if request.method == 'POST':
        new_qty = int(request.form['quantity'])
        cur.execute('''
          UPDATE Appears_In
          SET Quantity=%s
          WHERE BID=%s AND PID=%s
        ''', (new_qty, bid, pid))
        conn.commit()
        cur.close(); conn.close()
        return redirect(url_for('view_basket', bid=bid))

    cur.execute('''
      SELECT AI.Quantity, P.PName
      FROM Appears_In AI
      JOIN Product P ON AI.PID=P.PID
      WHERE AI.BID=%s AND AI.PID=%s
    ''', (bid, pid))
    item = cur.fetchone()
    cur.close(); conn.close()
    return render_template('edit_basket_item.html',
                           bid=bid, pid=pid, item=item)

# 7) DELETE AN ITEM FROM A BASKET
@app.route('/baskets/<int:bid>/items/<int:pid>/delete', methods=['POST'])
def delete_basket_item(bid, pid):
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute('DELETE FROM Appears_In WHERE BID=%s AND PID=%s', (bid, pid))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for('view_basket', bid=bid))


# — Appears_In (Basket Items) —

@app.route('/baskets/<int:bid>/items')
def list_items(bid):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        'SELECT P.PID, P.PName, AI.Quantity, AI.PriceSold '
        'FROM Appears_In AI '
        'JOIN Product P ON AI.PID=P.PID '
        'WHERE AI.BID=%s;',
        (bid,)
    )
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('items.html', bid=bid, items=items)

@app.route('/baskets/<int:bid>/items/new', methods=['GET','POST'])
def new_item(bid):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # figure out customer ID (if basket exists)
    cur.execute('SELECT CID FROM Basket WHERE BID=%s;', (bid,))
    row = cur.fetchone()
    existing_cid = row['CID'] if row else None

    if request.method == 'POST':
        cid = request.form.get('cid') or existing_cid
        pid = request.form['pid']
        qty = request.form['quantity']
        price = request.form['price']

        # auto-create basket if missing
        if not existing_cid:
            cur.execute(
                'INSERT INTO Basket (BID, CID) VALUES (%s, %s);',
                (bid, cid)
            )

        # insert item
        cur.execute(
            'INSERT INTO Appears_In (BID, PID, Quantity, PriceSold) '
            'VALUES (%s, %s, %s, %s);',
            (bid, pid, qty, price)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_items', bid=bid))

    # GET: load products and pass CID
    cur.execute('SELECT PID, PName, PPrice FROM Product;')
    products = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
        'new_item.html',
        bid=bid,
        products=products,
        cid=existing_cid
    )


# — Transactions CRUD —

@app.route('/transactions')
def list_transactions():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    # grab filters from URL
    customer = request.args.get('customer', '').strip()
    product  = request.args.get('product', '').strip()
    start    = request.args.get('start_date', '')
    end      = request.args.get('end_date', '')

    # base query
    sql = '''
      SELECT DISTINCT
        T.BID,
        T.CID,
        T.SAName,
        T.CCNumber,
        T.TDate,
        T.TTag,
        T.TotalAmount
      FROM `Transaction` T
      JOIN Appears_In AI ON T.BID = AI.BID
      JOIN Product P      ON AI.PID = P.PID
      WHERE 1=1
    '''
    params = []

    # apply filters
    if customer:
        if customer.isdigit():
            # numeric → filter by exact CID
            sql += ' AND T.CID = %s'
            params.append(int(customer))
        else:
            # text → fuzzy‐match on full name
            sql += '''
              AND EXISTS (
                SELECT 1
                  FROM Customer C
                 WHERE C.CID = T.CID
                   AND CONCAT(C.FName, " ", C.LName) LIKE %s
              )
            '''
            params.append(f"%{customer}%")

    if product:
        sql += ' AND P.PName LIKE %s'
        params.append(f"%{product}%")

    if start:
        sql += ' AND T.TDate >= %s'
        params.append(start)

    if end:
        sql += ' AND T.TDate <= %s'
        params.append(end)

    sql += ' ORDER BY T.TDate DESC;'

    cur.execute(sql, params)
    transactions = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
      'transactions.html',
      transactions=transactions,
      filters={
        'customer': customer,
        'product':  product,
        'start':    start,
        'end':      end
      }
    )


# — Statistics Dashboard —

@app.route('/statistics')
def statistics():
    return render_template('statistics.html')


@app.route('/stat_creditcard')
def stat_creditcard():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
      '''
      SELECT T.CCNumber,
             SUM(AI.Quantity * AI.PriceSold) AS total_charged
      FROM `Transaction` T
      JOIN Appears_In AI ON T.BID = AI.BID
      GROUP BY T.CCNumber
      ORDER BY total_charged DESC;
      '''
    )
    results = cur.fetchall()
    cur.close(); conn.close()
    return render_template('stat_creditcard.html', results=results)


@app.route('/stat_topcustomers')
def stat_topcustomers():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
      '''
      SELECT C.CID,
             CONCAT(C.FName, ' ', C.LName) AS name,
             SUM(AI.Quantity * AI.PriceSold) AS total_spent
      FROM Customer C
      JOIN Basket B      ON C.CID = B.CID
      JOIN Appears_In AI ON B.BID = AI.BID
      GROUP BY C.CID
      ORDER BY total_spent DESC
      LIMIT 10;
      '''
    )
    results = cur.fetchall()
    cur.close(); conn.close()
    return render_template('stat_topcustomers.html', results=results)


# — Stats: Most frequently sold products —
@app.route('/stat_freqproducts')
def stat_freqproducts():
    # 1. read date filters (default to all time)
    start = request.args.get('start_date', '2023-01-01')
    end   = request.args.get('end_date',   datetime.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT P.PID, P.PName, SUM(AI.Quantity) AS total_sold
        FROM Appears_In AI
        JOIN Product P ON AI.PID = P.PID
        JOIN `Transaction` T ON AI.BID = T.BID
        WHERE DATE(T.TDate) BETWEEN %s AND %s
        GROUP BY P.PID
        ORDER BY total_sold DESC;
    """, (start, end))
    results = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
      'stat_freqproducts.html',
      results=results,
      filters={'start': start, 'end': end}
    )


@app.route('/stat_distinctbuyers')
def stat_distinctbuyers():
    start = request.args.get('start_date', '2023-01-01')
    end   = request.args.get('end_date', datetime.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
        '''
        SELECT P.PID, P.PName, COUNT(DISTINCT T.CID) AS distinct_buyers
        FROM Appears_In AI
        JOIN Product P    ON AI.PID   = P.PID
        JOIN `Transaction` T ON AI.BID = T.BID
        WHERE DATE(T.TDate) BETWEEN %s AND %s
        GROUP BY P.PID
        ORDER BY distinct_buyers DESC;
        ''',
        (start, end)
    )
    results = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
        'stat_distinctbuyers.html',
        results=results,
        filters={'start': start, 'end': end}
    )


@app.route('/stat_maxbasket')
def stat_maxbasket():
    start = request.args.get('start_date', '2023-01-01')
    end   = request.args.get('end_date', datetime.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
        '''
        SELECT T.CCNumber, MAX(bt.total) AS max_basket
        FROM (
          SELECT BID, SUM(Quantity * PriceSold) AS total
          FROM Appears_In
          GROUP BY BID
        ) AS bt
        JOIN `Transaction` T ON bt.BID = T.BID
        WHERE DATE(T.TDate) BETWEEN %s AND %s
        GROUP BY T.CCNumber
        ORDER BY max_basket DESC;
        ''',
        (start, end)
    )
    results = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
        'stat_maxbasket.html',
        results=results,
        filters={'start': start, 'end': end}
    )


@app.route('/stat_avgprice')
def stat_avgprice():
    start = request.args.get('start_date', '2023-01-01')
    end   = request.args.get('end_date', datetime.today().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    cur.execute(
        '''
        SELECT P.PType, AVG(AI.PriceSold) AS avg_price
        FROM Appears_In AI
        JOIN Product P    ON AI.PID   = P.PID
        JOIN `Transaction` T ON AI.BID = T.BID
        WHERE DATE(T.TDate) BETWEEN %s AND %s
        GROUP BY P.PType;
        ''',
        (start, end)
    )
    results = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
        'stat_avgprice.html',
        results=results,
        filters={'start': start, 'end': end}
    )

@app.route('/transactions/new', methods=['GET','POST'])
def new_transaction():
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        bid         = request.form['bid']
        saname      = request.form['saname']
        ttag        = request.form['ttag']
        card_option = request.form.get('card_option', 'stored')

        # — Prevent duplicate placement: only one transaction per basket —
        cur.execute('SELECT COUNT(*) AS cnt FROM `Transaction` WHERE BID=%s;', (bid,))
        if cur.fetchone()['cnt'] > 0:
            cur.close()
            conn.close()
            return redirect(url_for('list_transactions'))

        # 1) Determine which card to use (stored vs new)
        if card_option == 'new':
            new_cc = {
                'CCNumber':       request.form['new_ccnumber'],
                'SecNumber':      request.form['new_secnumber'],
                'OwnerName':      request.form['new_ownername'],
                'CCType':         request.form['new_cctype'],
                'BillingAddress': request.form['new_billingaddr'],
                'ExpDate':        request.form['new_expdate']
            }
            cur.execute(
                '''INSERT INTO Credit_Card
                   (CCNumber, SecNumber, OwnerName, CCType, BillingAddress, ExpDate, StoredCardCID)
                   VALUES (%(CCNumber)s, %(SecNumber)s, %(OwnerName)s,
                           %(CCType)s, %(BillingAddress)s, %(ExpDate)s, NULL)''',
                new_cc
            )
            ccnumber = new_cc['CCNumber']
        else:
            ccnumber = request.form['ccnumber']

        # 2) Fetch customer status
        cur.execute(
            '''SELECT C.Status
               FROM Customer C
               JOIN Basket B ON C.CID=B.CID
               WHERE B.BID=%s;''',
            (bid,)
        )
        status = cur.fetchone()['Status']

        # 3) Load & re-price basket items for gold/platinum
        cur.execute('SELECT PID, Quantity FROM Appears_In WHERE BID=%s;', (bid,))
        items = cur.fetchall()

        # Clear out old PriceSold entries
        cur.execute('DELETE FROM Appears_In WHERE BID=%s;', (bid,))

        # Re-insert with correct pricing
        for it in items:
            pid, qty = it['PID'], it['Quantity']
            # check for an offer price
            price = None
            if status in ('gold','platinum'):
                cur.execute('SELECT OfferPrice FROM Offer_Product WHERE PID=%s;', (pid,))
                row = cur.fetchone()
                price = row['OfferPrice'] if row else None

            if price is None:
                cur.execute('SELECT PPrice FROM Product WHERE PID=%s;', (pid,))
                price = cur.fetchone()['PPrice']

            cur.execute(
                'INSERT INTO Appears_In (BID, PID, Quantity, PriceSold) VALUES (%s,%s,%s,%s);',
                (bid, pid, qty, price)
            )

        # 4) Compute TotalAmount
        cur.execute(
            'SELECT SUM(Quantity * PriceSold) AS total '
            'FROM Appears_In WHERE BID=%s;',
            (bid,)
        )
        total = cur.fetchone()['total'] or 0

        # 5) Insert the Transaction
        cur.execute(
            '''INSERT INTO `Transaction`
               (BID, CID, SAName, CCNumber, TTag, TotalAmount)
               VALUES (%s,
                       (SELECT CID FROM Basket WHERE BID=%s),
                       %s, %s, %s, %s);''',
            (bid, bid, saname, ccnumber, ttag, total)
        )

        # 6) Decrement stock quantities
        cur.execute(
            '''UPDATE Product P
               JOIN Appears_In AI ON P.PID=AI.PID
               SET P.PQuantity = P.PQuantity - AI.Quantity
               WHERE AI.BID=%s;''',
            (bid,)
        )

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_transactions'))

    # — GET: render the form —
    bid = request.args.get('bid')
    cur.execute('SELECT BID, CID FROM Basket;')
    baskets   = cur.fetchall()

    cur.execute(
        'SELECT CID, SAName '
        'FROM Shipping_Address '
        'WHERE CID=(SELECT CID FROM Basket WHERE BID=%s);',
        (bid,)
    )
    addresses = cur.fetchall()

    cur.execute(
        'SELECT CCNumber, CCType '
        'FROM Credit_Card '
        'WHERE StoredCardCID=(SELECT CID FROM Basket WHERE BID=%s);',
        (bid,)
    )
    cards     = cur.fetchall()

    cur.close()
    conn.close()
    return render_template(
        'new_transaction.html',
        baskets=baskets,
        addresses=addresses,
        cards=cards,
        selected_bid=bid
    )
# ─── Transactions: Edit ────────────────────────────────────────────────────────
@app.route('/transactions/<int:bid>/edit', methods=['GET','POST'])
def edit_transaction(bid):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # grab the updated fields from the form
        saname   = request.form['saname']
        ccnumber = request.form['ccnumber']
        ttag     = request.form['ttag']

        # update the row
        cur.execute(
            '''UPDATE `Transaction`
               SET SAName = %s,
                   CCNumber = %s,
                   TTag     = %s
               WHERE BID = %s;''',
            (saname, ccnumber, ttag, bid)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('list_transactions'))

    # — GET: render the edit form —
    cur.execute('''
      SELECT T.BID, B.CID, T.SAName, T.CCNumber, T.TTag
      FROM `Transaction` T
      JOIN Basket B ON T.BID = B.BID
      WHERE T.BID = %s;
    ''', (bid,))
    tx = cur.fetchone()

    # load that customer’s current addresses & cards
    cur.execute('SELECT SAName FROM Shipping_Address WHERE CID = %s;', (tx['CID'],))
    addresses = [r['SAName'] for r in cur.fetchall()]

    cur.execute('SELECT CCNumber, CCType FROM Credit_Card WHERE StoredCardCID = %s;', (tx['CID'],))
    cards = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
      'edit_transaction.html',
      tx=tx,
      addresses=addresses,
      cards=cards
    )


# ─── Transactions: Delete ──────────────────────────────────────────────────────
@app.route('/transactions/<int:bid>/delete', methods=['POST'])
def delete_transaction(bid):
    conn = get_db_connection()
    cur  = conn.cursor()

    cur.execute('DELETE FROM `Transaction` WHERE BID = %s;', (bid,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('list_transactions'))

@app.route('/customers/<int:cid>/transactions')
def customer_history(cid):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)
    # pull every transaction for this customer
    cur.execute('''
      SELECT T.BID, T.TDate, T.TTag, T.TotalAmount, T.SAName, T.CCNumber
      FROM `Transaction` T
      WHERE T.CID=%s
      ORDER BY T.TDate DESC
    ''', (cid,))
    transactions = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('customer_history.html',
                           cid=cid,
                           transactions=transactions)


@app.route('/cards/<ccnumber>/history')
def card_history(ccnumber):
    conn = get_db_connection()
    cur  = conn.cursor(dictionary=True)

    # Load all transactions that used this credit card
    cur.execute('''
      SELECT
        T.BID,
        T.CID,
        CONCAT(C.FName, ' ', C.LName) AS CustomerName,
        T.SAName,
        T.TDate,
        T.TTag,
        T.TotalAmount
      FROM `Transaction` T
      JOIN Customer C ON T.CID = C.CID
      WHERE T.CCNumber = %s
      ORDER BY T.TDate DESC;
    ''', (ccnumber,))

    transactions = cur.fetchall()
    cur.close()
    conn.close()

    return render_template(
      'card_history.html',
      card_number=ccnumber,
      transactions=transactions
    )

if __name__ == '__main__':
    app.run(debug=True)
