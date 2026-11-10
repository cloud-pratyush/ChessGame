"""
Chompy's Chess Castle - a kid-friendly chess game written in pure Python.
Runs in the browser (iPad Safari included) through Pyodide; see index.html.
You play White (the bottom pieces). Chompy the Dragon plays Black.
"""
import asyncio
import random
from js import document
from pyodide.ffi import create_proxy

# ---------------------------------------------------------------- chess engine
SOLID = {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
NAMES = {'P': 'pawn', 'N': 'horsey knight', 'B': 'slippery bishop',
         'R': 'castle tower', 'Q': 'queen', 'K': 'king'}
VAL = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0}
KN = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KG = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
OR = [(-1, 0), (1, 0), (0, -1), (0, 1)]
START = list("rnbqkbnr" + "pppppppp" + "." * 32 + "PPPPPPPP" + "RNBQKBNR")


class Pos:
    __slots__ = ("b", "turn", "castle", "ep")

    def __init__(self, b=None, turn='w', castle='KQkq', ep=-1):
        self.b = b[:] if b else START[:]
        self.turn, self.castle, self.ep = turn, castle, ep


def mine(p, color):
    return p != '.' and p.isupper() == (color == 'w')


def king_sq(b, color):
    return b.index('K' if color == 'w' else 'k')


def attacked(b, sq, by):
    """Is square `sq` attacked by color `by`?"""
    r, c = divmod(sq, 8)
    up = by == 'w'

    def P(ch):
        return ch if up else ch.lower()

    pr = r + 1 if up else r - 1
    if 0 <= pr < 8:
        for dc in (-1, 1):
            if 0 <= c + dc < 8 and b[pr * 8 + c + dc] == P('P'):
                return True
    for offs, ch in ((KN, 'N'), (KG, 'K')):
        for dr, dc in offs:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == P(ch):
                return True
    for dirs, pcs in ((DG, (P('B'), P('Q'))), (OR, (P('R'), P('Q')))):
        for dr, dc in dirs:
            rr, cc = r + dr, c + dc
            while 0 <= rr < 8 and 0 <= cc < 8:
                x = b[rr * 8 + cc]
                if x != '.':
                    if x in pcs:
                        return True
                    break
                rr += dr
                cc += dc
    return False


def pseudo(pos):
    b, t, out = pos.b, pos.turn, []
    opp = 'b' if t == 'w' else 'w'
    for i in range(64):
        p = b[i]
        if not mine(p, t):
            continue
        r, c = divmod(i, 8)
        u = p.upper()
        if u == 'P':
            d = -1 if t == 'w' else 1
            start = 6 if t == 'w' else 1
            lastrow = 0 if t == 'w' else 7
            r1 = r + d
            if 0 <= r1 < 8:
                pr = 'Q' if r1 == lastrow else ''  # pawns always become queens
                if b[r1 * 8 + c] == '.':
                    out.append((i, r1 * 8 + c, pr))
                    if r == start and b[(r + 2 * d) * 8 + c] == '.':
                        out.append((i, (r + 2 * d) * 8 + c, ''))
                for dc in (-1, 1):
                    cc = c + dc
                    if 0 <= cc < 8:
                        j = r1 * 8 + cc
                        if b[j] != '.' and not mine(b[j], t):
                            out.append((i, j, pr))
                        elif j == pos.ep:
                            out.append((i, j, ''))
        elif u in 'NK':
            for dr, dc in (KN if u == 'N' else KG):
                rr, cc = r + dr, c + dc
                if 0 <= rr < 8 and 0 <= cc < 8:
                    j = rr * 8 + cc
                    if not mine(b[j], t):
                        out.append((i, j, ''))
            if u == 'K':
                base = 60 if t == 'w' else 4
                R = 'R' if t == 'w' else 'r'
                if i == base and not attacked(b, i, opp):
                    if (('K' if t == 'w' else 'k') in pos.castle
                            and b[base + 1] == '.' and b[base + 2] == '.' and b[base + 3] == R
                            and not attacked(b, base + 1, opp) and not attacked(b, base + 2, opp)):
                        out.append((i, base + 2, ''))
                    if (('Q' if t == 'w' else 'q') in pos.castle
                            and b[base - 1] == '.' and b[base - 2] == '.' and b[base - 3] == '.'
                            and b[base - 4] == R
                            and not attacked(b, base - 1, opp) and not attacked(b, base - 2, opp)):
                        out.append((i, base - 2, ''))
        else:
            dirs = DG if u == 'B' else OR if u == 'R' else DG + OR
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while 0 <= rr < 8 and 0 <= cc < 8:
                    j = rr * 8 + cc
                    x = b[j]
                    if x == '.':
                        out.append((i, j, ''))
                    else:
                        if not mine(x, t):
                            out.append((i, j, ''))
                        break
                    rr += dr
                    cc += dc
    return out


def apply(pos, m):
    f, t, promo = m
    b = pos.b[:]
    p = b[f]
    u = p.upper()
    white = pos.turn == 'w'
    if u == 'P' and t == pos.ep:
        b[t + 8 if white else t - 8] = '.'
    b[t] = p
    b[f] = '.'
    if promo:
        b[t] = 'Q' if white else 'q'
    if u == 'K' and abs(t - f) == 2:
        if t > f:
            b[f + 1], b[f + 3] = b[f + 3], '.'
        else:
            b[f - 1], b[f - 4] = b[f - 4], '.'
    cs = pos.castle
    for s in (f, t):
        if s == 60:
            cs = cs.replace('K', '').replace('Q', '')
        elif s == 4:
            cs = cs.replace('k', '').replace('q', '')
        elif s == 63:
            cs = cs.replace('K', '')
        elif s == 56:
            cs = cs.replace('Q', '')
        elif s == 7:
            cs = cs.replace('k', '')
        elif s == 0:
            cs = cs.replace('q', '')
    ep = (f + t) // 2 if u == 'P' and abs(t - f) == 16 else -1
    return Pos(b, 'b' if white else 'w', cs, ep)


def legal(pos):
    me = pos.turn
    opp = 'b' if me == 'w' else 'w'
    res = []
    for m in pseudo(pos):
        np_ = apply(pos, m)
        if not attacked(np_.b, king_sq(np_.b, me), opp):
            res.append(m)
    return res


def in_check(pos):
    opp = 'b' if pos.turn == 'w' else 'w'
    return attacked(pos.b, king_sq(pos.b, pos.turn), opp)


def insufficient(pos):
    rest = [p.upper() for p in pos.b if p not in '.kK']
    return len(rest) == 0 or (len(rest) == 1 and rest[0] in 'NB')


def game_status(pos):
    if not legal(pos):
        return 'mate' if in_check(pos) else 'stale'
    if insufficient(pos):
        return 'draw'
    return None


# ------------------------------------------------------------------- computer
def evaluate(pos):
    s = 0
    for i, p in enumerate(pos.b):
        if p == '.':
            continue
        u = p.upper()
        r, c = divmod(i, 8)
        white = p.isupper()
        v = VAL[u]
        if u == 'P':
            v += (7 - r if white else r) * 6
        elif u in 'NBQ':
            v += (6 - (abs(r - 3.5) + abs(c - 3.5))) * 5
        s += v if white else -v
    return s if pos.turn == 'w' else -s


def order(pos, m):
    t = pos.b[m[1]]
    score = VAL[t.upper()] * 10 - VAL[pos.b[m[0]].upper()] if t != '.' else 0
    return score + (800 if m[2] else 0)


def negamax(pos, depth, alpha, beta):
    if depth == 0:
        return evaluate(pos)
    ms = legal(pos)
    if not ms:
        return -50000 - depth if in_check(pos) else 0
    ms.sort(key=lambda m: -order(pos, m))
    best = -10 ** 9
    for m in ms:
        v = -negamax(apply(pos, m), depth - 1, -beta, -alpha)
        if v > best:
            best = v
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def pick_move(pos, level):
    ms = legal(pos)
    if level == 'easy':
        caps = [m for m in ms if pos.b[m[1]] != '.']
        if caps and random.random() < 0.4:
            return random.choice(caps)
        return random.choice(ms)
    depth, noise = {'medium': (2, 60), 'hard': (3, 8), 'hint': (2, 0)}[level]
    best, bv = None, -10 ** 9
    for m in ms:
        v = -negamax(apply(pos, m), depth - 1, -10 ** 9, 10 ** 9) + random.uniform(0, noise)
        if v > bv:
            best, bv = m, v
    return best


# ------------------------------------------------------------- funny messages
OPEN = ["Welcome, brave hero! I'm Chompy the Dragon and I eat pawns for breakfast. Your move! 🍳",
        "Greetings, tiny genius! Chompy is hungry for victory (and cookies). Let's play! 🍪"]
QUIET = ["Ooh, sneaky! My dragon tummy is rumbling...", "Nice move! Did a wizard teach you that? 🧙",
         "That pawn just did a happy dance 💃", "Bold! Even my grandma dragon is impressed. 👵🐉",
         "Careful... my scales are tingling! ✨", "Hmm! Plot twist! 🎬"]
P_CAP = ["CHOMP! You gobbled my {v}! Rude! 😤", "Hey! That {v} was my best friend! 😭",
         "My {v} says 'Bye bye!' 👋 Well played.", "You ate my {v}! I'm calling the dragon police! 🚨"]
C_CAP = ["Nom nom nom! I ate your {v}! 😋", "Your {v} tasted like chicken 🍗",
         "Oopsie! Your {v} went to Pizza Land 🍕", "Burp! Excuse me. Thanks for the {v}! 🤭"]
P_CHECK = " And you poked my king! 😱 He's hiding!"
C_CHECK = ["Eeek-a-boo! I'm poking your King! Can you save him? 👑", "CHECK! Your king needs a hug and a hiding spot! 🫂"]
THINK = ["Hmm... using my dragon brain 🧠🔥", "Thinking... pondering... snacking... 🍪",
         "Wait, I'm asking my pet goldfish 🐟", "Beep boop... computing silliness 🤖"]
CASTLE_MSG = "Castling! Your king is tucked in cozy like a burrito 🌯"
C_CASTLE = "I castled! My king is snug in his dragon cave 🏰"
PROMO_MSG = "WOW! Your pawn became a QUEEN! Fancy hat! 👑✨"
C_PROMO = "Muahaha! My pawn grew up into a QUEEN! 👑😈"
ILLEGAL = ["Whoopsie! That piece can't go there. Try again! 🙈", "Nope nope nope! The chess police say no! 🚓",
           "Pieces have rules too! Pick a dotted square. 🔵"]
STUCK = "That piece is stuck like a sock in a toaster! Try another! 🧦"
HINTS = ["Psst... try the glowing squares! 🤫 (Don't tell Chompy!)",
         "My crystal ball says... 🔮 move from one glowing square to the other!"]
WIN = "🎉 CHECKMATE! YOU WIN! You're the Chess Champion of the Universe! 🏆"
LOSE = "😈 CHECKMATE! I win this time! But you were awesome. Rematch?"
STALE = "🤝 Stalemate! Nobody can move... it's a draw, like a tickle fight with no winner!"
DRAW = "🤝 Not enough pieces to win. It's a draw! High five! ✋"

MISSIONS = [
    ("🐴 Horsey Ninja: Capture any piece with a KNIGHT!", lambda e: e['piece'] == 'N' and e['cap']),
    ("🏰 Castle Hero: Tuck your king in safely by CASTLING!", lambda e: e['castle']),
    ("😈 Sneaky Boo: Say 'BOO!' to Chompy's king by giving CHECK!", lambda e: e['check']),
    ("🐛 Pawn Parade: March a pawn up to the 5th row!", lambda e: e['piece'] == 'P' and e['to_rank'] >= 5),
    ("🍪 Cookie Monster: Gobble up any piece!", lambda e: bool(e['cap'])),
    ("👑 Queen Quest: Capture something with your QUEEN!", lambda e: e['piece'] == 'Q' and e['cap']),
    ("🦄 Bishop Zoom: Capture something with a BISHOP!", lambda e: e['piece'] == 'B' and e['cap']),
    ("🚀 Rook Rocket: Capture something with a ROOK!", lambda e: e['piece'] == 'R' and e['cap']),
]

# ------------------------------------------------------------------ game state
pos = Pos()
selected = None
last = ()
hint = set()
hist = []
won_w = []   # black pieces YOU captured
won_b = []   # white pieces CHOMPY captured
busy = False
over = False
end_text = ""
stars = 0
mission_order = list(range(len(MISSIONS)))
mission_i = 0
toast_id = 0


def el(i):
    return document.getElementById(i)


def say(text, face='🐲'):
    b = el("bubble")
    b.textContent = text
    b.style.animation = 'none'
    _ = b.offsetHeight
    b.style.animation = ''
    el("face").textContent = face


async def toast(text):
    global toast_id
    toast_id += 1
    mine_id = toast_id
    t = el("toast")
    t.textContent = text
    t.classList.add("show")
    await asyncio.sleep(3)
    if mine_id == toast_id:
        t.classList.remove("show")


async def clear_confetti():
    await asyncio.sleep(5)
    el("confetti").innerHTML = ""


def confetti():
    em = ['🎉', '⭐', '🎈', '🍪', '🦄', '🐲', '✨', '🏆']
    el("confetti").innerHTML = ''.join(
        f'<span style="left:{random.randint(0, 95)}%;animation-delay:{random.random() * 1.5:.2f}s;'
        f'font-size:{random.randint(24, 44)}px">{random.choice(em)}</span>' for _ in range(40))
    asyncio.ensure_future(clear_confetti())


def level():
    return el("level").value


def tray(lst, cls):
    rank = {'Q': 0, 'R': 1, 'B': 2, 'N': 3, 'P': 4}
    s = ''.join(f'<span class="pc {cls}">{SOLID[x]}\uFE0E</span>' for x in sorted(lst, key=rank.get))
    return s or '<span class="none">none yet</span>'


def render_trays():
    you = sum(VAL[x] for x in won_w) // 100
    chompy = sum(VAL[x] for x in won_b) // 100
    d = you - chompy
    lead = "all square" if d == 0 else (f"you lead by {d} ⭐" if d > 0 else f"Chompy leads by {-d}")
    el("trays").innerHTML = (
        f'<div class="tray"><b>🧒 You</b> <small>({lead})</small>'
        f'<div>🍪 Won: {tray(won_w, "b")}</div><div>😢 Lost: {tray(won_b, "w")}</div></div>'
        f'<div class="tray"><b>🐲 Chompy</b>'
        f'<div>🍪 Won: {tray(won_b, "w")}</div><div>😢 Lost: {tray(won_w, "b")}</div></div>')


def render():
    ms = legal(pos) if not over else []
    targets = {m[1] for m in ms if selected is not None and m[0] == selected}
    chk = king_sq(pos.b, pos.turn) if in_check(pos) else -1
    cells = []
    for i in range(64):
        r, c = divmod(i, 8)
        cls = 'sq ' + ('l' if (r + c) % 2 == 0 else 'd')
        if i == selected:
            cls += ' sel'
        if i in last:
            cls += ' last'
        if i == chk:
            cls += ' chk'
        if i in hint:
            cls += ' hint'
        p = pos.b[i]
        inner = ''
        if p != '.':
            inner += f'<span class="pc {"w" if p.isupper() else "b"}">{SOLID[p.upper()]}\uFE0E</span>'
        if i in targets:
            inner += f'<i class="dot{" cap" if p != "." else ""}"></i>'
        cells.append(f'<div class="{cls}" data-sq="{i}">{inner}</div>')
    el("board").innerHTML = ''.join(cells)
    if over:
        txt = end_text
    elif busy:
        txt = "🐲 Chompy is thinking..."
    elif chk >= 0:
        txt = "⚠️ CHECK! Save your king! 👑"
    else:
        txt = "🧒 Your turn! Tap a piece."
    el("status").textContent = txt
    el("stars").textContent = f"⭐ Stars: {stars}"
    render_trays()
    m = MISSIONS[mission_order[mission_i % len(MISSIONS)]]
    el("mission").textContent = "🎯 Mission: " + m[0]


def make_move(m):
    """Play move m on the global position and describe what happened."""
    global pos, last, hint
    f, t, pr = m
    p = pos.b[f]
    u = p.upper()
    cap = pos.b[t]
    if u == 'P' and t == pos.ep and cap == '.':
        cap = 'p'
    new = apply(pos, m)
    if cap != '.':
        (won_w if pos.turn == 'w' else won_b).append(cap.upper())
    ev = dict(piece=u, cap='' if cap == '.' else cap.upper(),
              castle=(u == 'K' and abs(t - f) == 2), promo=bool(pr),
              check=in_check(new), to_rank=8 - t // 8)
    pos, last, hint = new, (f, t), set()
    return ev


def reaction(ev, player):
    if ev['promo']:
        msg = PROMO_MSG if player else C_PROMO
    elif ev['castle']:
        msg = CASTLE_MSG if player else C_CASTLE
    elif ev['cap']:
        msg = random.choice(P_CAP if player else C_CAP).format(v=NAMES[ev['cap']])
    elif ev['check'] and not player:
        return random.choice(C_CHECK)
    else:
        msg = random.choice(QUIET) if player else random.choice(QUIET)
    if ev['check'] and player:
        msg += P_CHECK
    elif ev['check']:
        msg += " " + random.choice(C_CHECK)
    return msg


def finish(st, mover):
    global over, end_text, stars
    over = True
    if st == 'mate' and mover == 'w':
        stars += 3
        end_text = "🏆 You won! +3 stars"
        say(WIN, '🥳')
        confetti()
    elif st == 'mate':
        end_text = "Chompy won. Rematch?"
        say(LOSE, '😈')
    elif st == 'stale':
        end_text = "Draw!"
        say(STALE, '🤝')
    else:
        end_text = "Draw!"
        say(DRAW, '🤝')


async def player_move(m):
    global busy, selected, stars, mission_i
    busy = True
    selected = None
    hist.append((pos, last, won_w[:], won_b[:]))
    ev = make_move(m)
    mission = MISSIONS[mission_order[mission_i % len(MISSIONS)]]
    if mission[1](ev):
        stars += 1
        mission_i += 1
        asyncio.ensure_future(toast("⭐ MISSION COMPLETE! You earned a star! ⭐"))
    st = game_status(pos)
    if st:
        busy = False
        render()
        finish(st, 'w')
        return
    say(reaction(ev, True) + "\n\n" + random.choice(THINK), '😋' if ev['cap'] else '🐲')
    render()
    await asyncio.sleep(0.4)
    m2 = pick_move(pos, level())
    ev2 = make_move(m2)
    st = game_status(pos)
    busy = False
    render()
    if st:
        finish(st, 'b')
        return
    say(reaction(ev2, False), '😋' if ev2['cap'] else '🐲')


def on_click(event):
    global selected
    if busy or over:
        return
    node = event.target.closest(".sq")
    if node is None:
        return
    sq = int(node.getAttribute("data-sq"))
    p = pos.b[sq]
    ms = legal(pos)
    if selected is not None:
        for m in ms:
            if m[0] == selected and m[1] == sq:
                asyncio.ensure_future(player_move(m))
                return
    if p != '.' and p.isupper():
        if any(m[0] == sq for m in ms):
            selected = sq
        else:
            selected = None
            say(STUCK, '🙈')
    else:
        if selected is not None:
            say(random.choice(ILLEGAL), '🙈')
        selected = None
    render()


def on_hint(event):
    global hint
    if busy or over:
        return
    m = pick_move(pos, 'hint')
    hint = {m[0], m[1]}
    say(random.choice(HINTS), '🔮')
    render()


def on_undo(event):
    global pos, last, selected, hint, over
    if busy or not hist:
        return
    pos, last, w, b = hist.pop()
    won_w[:], won_b[:] = w, b
    selected, hint, over = None, set(), False
    el("confetti").innerHTML = ""
    say("Time travel! ⏪ Poof! Do-over!", '🧙')
    render()


def new_game(event=None):
    global pos, selected, last, hint, hist, busy, over, mission_i
    pos, selected, last, hint, hist = Pos(), None, (), set(), []
    won_w.clear()
    won_b.clear()
    busy, over, mission_i = False, False, 0
    random.shuffle(mission_order)
    el("confetti").innerHTML = ""
    say(random.choice(OPEN))
    render()


el("board").addEventListener("click", create_proxy(on_click))
el("btn-new").addEventListener("click", create_proxy(new_game))
el("btn-undo").addEventListener("click", create_proxy(on_undo))
el("btn-hint").addEventListener("click", create_proxy(on_hint))
new_game()
