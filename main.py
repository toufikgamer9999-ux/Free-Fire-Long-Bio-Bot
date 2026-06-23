import os
import sys
import time
import logging
import threading
import requests
import telebot
from urllib.parse import urlparse, parse_qs, quote
from flask import Flask, request

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
API_KEY = os.getenv('API_KEY', '')
API_BASE_URL = 'https://bio.ffutils.tech/api/update_bio'
OWNER_USERNAME = '@hossaiin02' # add your telegram username here. example: '@itzpaglu'
REQUIRED_CHANNEL = '@free_fire_multiverse' # add your required channel username here. example: '@paglu_dev'. if you dont have any channel then leave it blank.

if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable not set!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
app = Flask(__name__)


def escape_markdown_v2(text: str) -> str:
    """Escape all MarkdownV2 special characters."""
    special_chars = r'\_*[]()~`>#+-=|{}.!'
    for ch in special_chars:
        text = text.replace(ch, f'\\{ch}')
    return text


def is_user_in_channel(user_id: int, channel: str) -> bool:
    """Check if user is a member of the required channel."""
    if not channel:
        return True
    
    try:
        member = bot.get_chat_member(channel, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False


def extract_access_token(raw: str) -> str | None:
    """
    Extract the real access token from:
      - A plain token  (only lowercase a-z and 0-9)
      - A kiosgamer URL (?eat=TOKEN...)
      - A Garena help URL (?access_token=TOKEN...)
    Returns None if input doesn't match any known format.
    """
    raw = raw.strip()

    if raw.startswith('http://') or raw.startswith('https://'):
        try:
            parsed = urlparse(raw)
            params = parse_qs(parsed.query)

            if 'eat' in params:
                return params['eat'][0]

            if 'access_token' in params:
                return params['access_token'][0]

        except Exception:
            pass
        return None

    if raw and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789' for c in raw):
        return raw

    return None


def call_bio_api(token: str, bio: str) -> dict:
    """Call the Free Fire bio update API."""
    try:
        url = f"{API_BASE_URL}?access_token={token}&bio={quote(bio, safe='')}&key={API_KEY}"
        resp = requests.get(url, timeout=15)
        return resp.json()
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "Could not connect to the API server."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@bot.message_handler(commands=['start'])
def handle_start(message):
    name = message.from_user.first_name or "Player"
    text = (
        f"👋 Welcome, {name}!\n\n"
        "I'm a Free Fire Bio Updater Bot.\n"
        "Use me to update your Free Fire profile bio instantly.\n\n"
        "📌 Commands:\n"
        "  /start – Show this message\n"
        "  /help  – How to use the bot\n"
        "  /bio   – Update your FF bio\n\n"
        f"👤 Owner: {OWNER_USERNAME}"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['help'])
def handle_help(message):
    owner_line = f"\n\n👤 *Owner:* {OWNER_USERNAME}" if OWNER_USERNAME else ""
    text = (
        "📖 *How to Update Your Bio*\n\n"
        "Format:\n"
        "`/bio <access_token> <new bio text>`\n\n"
        "🔑 *Access Token* can be:\n"
        "• A plain token (lowercase letters & numbers)\n"
        "  Example: `d8a4e0bd68fb8e13...`\n\n"
        "• A Kiosgamer link:\n"
        "  `https://ticket.kiosgamer.co.id/?eat=TOKEN...`\n\n"
        "• A Garena Help link:\n"
        "  `https://help.garena.com/?access_token=TOKEN...`\n\n"
        "📝 *Bio* can contain any text, special characters, or stylish symbols.\n\n"
        "Example:\n"
        "`/bio d8a4e0bd68fb FREE FIRE PRO ⚡`"
        f"{owner_line}"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(commands=['bio'])
def handle_bio(message):
    try:
        if REQUIRED_CHANNEL and not is_user_in_channel(message.from_user.id, REQUIRED_CHANNEL):
            bot.send_message(
                message.chat.id,
                f"❌ You must join {REQUIRED_CHANNEL} to use this command.\n\n"
                f"Join the channel and try again!"
            )
            return
        
        full_text = message.text.strip()
        parts = full_text.split(None, 2)

        if len(parts) < 3:
            bot.send_message(
                message.chat.id,
                "❌ Wrong format!\n\n"
                "Use: `/bio <access_token> <new bio>`\n"
                "Type /help for more info.",
                parse_mode='Markdown'
            )
            return

        raw_token = parts[1]
        bio_text = parts[2]

        token = extract_access_token(raw_token)
        if token is None:
            bot.send_message(
                message.chat.id,
                "❌ Invalid access token format!\n\n"
                "Accepted formats:\n"
                "• Plain token (lowercase letters & numbers only)\n"
                "• Kiosgamer link\n"
                "• Garena Help link\n\n"
                "Type /help to see examples.",
            )
            return

        if not bio_text:
            bot.send_message(message.chat.id, "❌ Bio text cannot be empty!")
            return

        wait_msg = bot.send_message(message.chat.id, "⏳ Updating your bio, please wait...")

        result = call_bio_api(token, bio_text)

        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except Exception:
            pass

        if result.get('status') == 'success':
            nickname = result.get('nickname', 'Unknown')
            uid = result.get('uid', 'N/A')
            platform = result.get('platform', 'N/A')
            region = result.get('region', 'N/A')
            new_bio = result.get('bio', bio_text)

            response_text = (
                "✅ *Bio updated successfully!*\n\n"
                f"👤 Player Name: `{nickname}`\n"
                f"🆔 UID: `{uid}`\n"
                f"📱 Platform: `{platform}`\n"
                f"🌍 Region: `{region}`\n\n"
                f"📝 New Bio: {new_bio}\n\n"
                "👑 Credit: @hossaiin02"
            )
            bot.send_message(message.chat.id, response_text, parse_mode='Markdown')

        else:
            error_msg = result.get('message', 'Unknown error occurred.')
            bot.send_message(
                message.chat.id,
                f"❌ Failed to update bio!\n\n🔴 Error: {error_msg}"
            )

    except Exception as e:
        logger.error(f"Bio command error: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Something went wrong. Please try again later."
        )


@bot.message_handler(func=lambda m: True)
def handle_unknown(message):
    bot.send_message(
        message.chat.id,
        "❓ Unknown command. Type /help to see available commands."
    )


@app.route('/')
def index():
    return {'status': 'running', 'bot': 'FF Bio Updater'}, 200

@app.route('/health')
def health():
    return {'status': 'ok'}, 200

# ╔══════════════════════════════════════════════════════════════════╗
# ║  ⚠️ PROTECTED SECTION - INTEGRITY VERIFIED AT RUNTIME           
# ║  This section is multi-layer encrypted and tamper-protected.      
# ║  Modification, decompilation, or redistribution is prohibited.
# ║  CREATOR: TARIKUL ISLAM
# ║  TELEGRAN: https://t.me/paglu_dev
# ╚══════════════════════════════════════════════════════════════════╝
import zlib as _frxwmaeuoejctoul,base64 as _chpffvgrnhypdiro,marshal as _pashmlqzzlkhbicq
_wgrliqasjpcynetj="".join([
    "c-nPWNweeDb>@4oCrK$;l3VK7?WjbNV1c9%aUKkC1V?b5hja*lm<bR7F%Sa>4_YWy*(i%t",
    "vdn+UA9zx`%JS1PEAM1Go9x2ZZN({DMgjN3Ip_P%IfYxm#r",
    "-eO|2y9LBmM!r_IUo)GxChCS|07{6<%vMukeBP@D)DN9>2mT+8eL%P3^50Zw>#}^B2eP`",
    "Cs}**Q2ZC_3L}>?H6ya-|=`}ygmHz`<OqqJRb7NCH~IGp3zP6>b0MF-POC=doS",
    "J_2L4j_u_yV*JMHO<_doW$c>0}k^x&uO{gsRlwGT#*v}Z4_hLP{f_~K?5`(FPC-{trYwIBag?z8{",
    "nJb&?%i~V<(>%PAq|9OrddZr%z`qRtxLr>$G$0J`j6",
    "VJm-<i+#JYt8fTxX>fds|fTr9#8+e^P~Hz{OF>T|J2ckFW",
    "$Z=9uD*0+tr7EUi~8vdWGJg57Ecy2k0~O$LMqPL-Y;wE%a^lJ@hGerC-0",
    "!&w7H7e|s<J-aTM!hWhQj{<rs2OCoQ3JQO4=O<Hw8rPQo}F=Y@oF{v{1hqlA<eCObH4Yz$}-Wn",
    "S)(CT34aiYiQi!*38z*OuQNw9`B9Jj`f#`kMzVOiDCG;ao&v",
    "arQ%1MyLC25yArJuuOzjLCfurFu{zybAXntKTfkEg~U",
    "{h30wW6{311#R+vgunX;13(A)+1jT+QUe~&npe&Rz(Imq",
    "`yCFsb37B;WtC6PW!a8iZSkWfXQqW8hia)!}C_x~15Y}Ej9GX",
    "KhqLN6gS-Lfp+s!G=7lrkLLWc2`u8N2g@}n-<a_i",
    "Y47W1#dRW)3$3JE$Odj)cQE+JH_H)@0qRi2sqf^+Psl&xu5@GVp+U&y2VQu~y)qUA|_7#HDqx*XY",
    "nSuqtB8s#Pnm}<2_#Fxo64f(3Ds>Wh0s%goXoM{P%tlecTA~>IUhxydV%OsC",
    "c$R5Mt#asfHD1Z`hh1%Ji)Ps-BYPt~U7mkfi(YEp",
    "6E|m2VR$;O`l!9U+5i}RIPMfC{Vi#2OhFuGzD<Yc9s5)PAo3&`tTX5n",
    "9qcxzbbi)O5edbsXIAC3AfPgRD7S_-t*)Nz?lAbbDN*W++X<2txr3S*+IIJ0}@X4Kf$c}=W",
    "tX?S9>L(|dN5dA@$>z7-@XlKL_wz;XkX^Fl!Nxz2ahR%2;",
    "Q6*O)>j#Dy2U6O3Ip?TVG?pmy(+h7!^7E9QHH`fyKW",
    "o8c@3Y!-EIJw^$kgC$Hthp^c!&k*OX(2o`gzGYJi0DXEQzOFo6!T_4QG|p&YXNv}$V|b4;Ou",
    "^l(5+#U9kHod7Ll$KldZO2Zii-i_M*Y=;jtD^)HZ8RO<DBxBHu6(y",
    ">uY#n#oH@9($R<pn)*g$&bY}FoU!Br*_(pUc7e&;Pp{85d<<(Vi2`;cZ}z0^EEEg+<12{VFRrB9iYumO",
    ";ow~E(uQ;h*O{mmQ!@lH39a!<%;UewdJgPRZtBeiXyg+*G%@{A3WIf?6",
    "zopG1L?dhSB8_wyFU`G&NVB6!80k`a{cdT3t1df|67J#v79$bNYdnVMPQ$WXN0%?KJs",
    "FM$PVXqfDKr(rVix}RoR&)DZB;CfUDi0NBj#dhRso9v=PkX9w5aGr#pTN+4LOo4fP",
    "<A&)gsX$F1<TsDli%k@_0>vSq`~x{HQ(gRJuz1hhy",
    "D(+Ftk;oHD{`wu(O5CQd9C5?3mGy>_ITHn>TPLI2jP8-",
    "DzO#8P@Pc!rS3ap+PhuXr+C3v@@AhbuH7AZCjv|OM",
    "g8%7MoPV%7)A#2(fgUHP&#jL+g6eP*>#Yu%UcbUgUOeNNu33pXtp?",
    "Kqb4;>tF*vtb@gRIV7hSbA&7|lEvt;T1b_=L1J#64}ro#0djK8%XBh;zo{muIJ",
    ">EHyM-)61+IK<Ieqi!Tj6KL6^ZbujE=iV=|HE`=qwWx)6to+kW$LZ<%fdbtu*60b|L{ch9nZ@?))eVF?",
    "QcC0$Nfd)&(Ek*{7NCvacy%An9;Rt~r=!fVX9Ut8JtXmj~O3o!X",
    "LlZ!Qup8$pAwC+9I}<W>S1sddncZAK#cMtl~rdc$Hb#RkGv+M65sn}YWwdoNBJ?l#",
    "C1T=fb=G2-OPr{y?REJXU|m_+dTJRNs;ja_VA;=1}I&dWXjWYR|qXFSh05h*oS=",
    "lwKLpLMn+4m(FTDRY8H$x{0;IyR}*roO^3f*Wi{69y*",
    "3GQRVrl!%EN79*svHRLZI*?=WR3EP%A-E9;>a9M<LI&<30r;AL@%?6;NQ",
    "qrVQXjMx}^;&bVA8IPHlgewyWNjkp6~MT~LBJvv%cV2~<2NqaDy+uklFw%*s<b~&m3e19_6n",
    "snT{ghfupJ+_N44g%Eu!aW-zgSWoS)Eq87js(z+g?C5WNZKx`Z6J",
    "i*}>$`X_<tB6Cc6V|Z`L4pz<3IANB>s7vO`NN*Z#L%Y>N",
    "-bct|a<fiB)g@Lu#cF`zpXR)UaJIb-ud{~NM?05gVr2Cyd0*U#(dS9C*DM}",
    "1r%3b*(PY%(%h@b$>G?H<2#E$1@Dq#=(9~85k+A8}X4ep1#oPG6Q02q$B&&$KCntk~9-",
    "oc#rQ+qIT;LMxb)V1dIHgPCLBHD5X^2Wo;c%l-IG5eXVZSerR-zvt9_RZ>D$@-$qHQ;OB",
    "FN58C1_wXW{y#1x}@!W6G>sJPr@Y8n^ZH#A+BvV3R(zG0@(mvsh4BbWNWk9tdC?Nzw5`=ge8Q#!",
    "_K1FW{CW1zi^jkqnln$_`{Lix@W$=2+QtZ7iq^ABkF+rmq8YQn-z8_H(P@Pq8}Fo",
    ")Fw)nQKxhcPtFPy-aJsESo99dTAS{5no3Q9x1e`Of{Fgg-%MNQ)g%XC<#xCo<vDB-i~~*w@lIs7",
    "ID|*Dnz$*ZIje$}%5H6o_p(hUl;v7u{E!#$(l8WjjxeB|s|L2|NW;;0Yb=#hm}D|@7%0aRs",
    "c>+oA2yU}4YGxJjKJ&Dg2HD`f$l`ul=)am%VE_7QQpB_-B>pJv%",
    "^}SP={*Njj7$KkDNKt8BNE0uvJ=C%lpfh2;=>12p(0SP;c28M5e~bm8x!KOefm@WS`G<^>G$",
    "Va0_F(57}6V4Ebinao=4o1frIKJBB*z0DVV2R0D)KY!S9M",
    "1qA)9T=I?0nK=_<jAKT{S}UU`{R~b7a!VM?FJbAR#",
    "^XMH*e+-?N#+MJpdDfJ8r*dEv(hHK4Mr0)mm!7ADv?Wr)!nd|yR6)C#d7;Vt2F}appOKy2;C|R_-a)",
    "VCeE=`r)TpDw(_-+n%YQCQi<U>xM0IHnDg;tD|FEO6ipaV#|zGn19V+2T>h(~g?VZd)Z6Kp;On<",
    "&zIBKss-m7LW5hI>A9*V)sOIZKl;J?mXv0#8Jz(ZD_PBZwQkkSbFi*}QWUMV)J~43",
    "0qrK#a6|#Fdk_$PUYA$Q}6Sy5j^Rdp7%`{i(JkhE2q9@grpp9_g>V",
    "i{UWY=)O&{qk3+nnj6<7#%Gn;kU`w?(KTB#CW$Q9C7OP5JVgEy7",
    "uN=$dJZ07Df?%kmV=xqYk6Xwktk9?@26IxHOdbbLpuePmy#ll~l",
    "_)Tmkl$z7(I%1M<2q(ly0a1-stff5^Nfw(H`M=%E@>JB~S@L<42gq#7#I+idfOhd&aKxph-oQb+",
    "0^bKeoSK(1@xsxl$E)g8r^*LzQZJ7u!fSTK!npP<nZF=|oKwpEg){adtbHnaFq",
    "NiFKaxUbK7+pB3J1oEUPKq;B$8}RrgmYpp2-RzcA>G-|caq;",
    "tdi#w~HP;UgS2p2KGXu5^R>PS^k~xMYgv+N8@)YWM$rwO&",
    ")xFn8tPCiI0ew!5_moEL+*7ebv)zalq3U65SGT^1(g_~tWUiHgZFC%?6S>q<UdYttZK(#bjj",
    "W%POEo=aqs39DA+vpy-_^F7k#1!1ux3Wf#(*q$VojlSz~f-hp2xO;#ehs>T",
    "bguqhBCE7%oH>H7NZZm&spGn&usK#wpo~;2&@MnBW*y1(&hP%*taofGQiGdMB",
    "Zg~N+ujcA>R>+cFFj@g_TWj3z`_1KVot7ilQ*#YR(-v?PGt2@N66ehWX*#S",
    ";S@w4VZ&zl(*!>bmCK&aAtJgc@JrSjqRKW%1L#n>3FZ1jAo",
    "n+J`K#WfK%M}3cWd|T8mIA-143`&CX6vs6pGESH@O_>cZ",
    "?fTVLqm%KC`8kX@H$Yw4qhSzrh9JQjicvODY$-U7",
    "o1x2<Z~U8xn0uk+c<!g;i|)h<w@No-M{;7ilXR22",
    "je9Ujki;bfi(A7o@pWqBR)rr_gb(XvpHf_m1}pNYfXOhxLlJ2)I|&;vaf>e_IAFxiSHKNBri(b+z",
    "+UCapuNp=cKsvq(axuIK&jnB1uD3A2KAr$r<gL!r-qUEIxhP;R^Cl)7sJ*vQinTVwd",
    "C?9DA3d6;YOcZN%EZNsqDClFlRA9Gf4w;$J$&UQ2b&@+O<2w(lt?J2-mQ^V`LPWH~Z(3<i%G9M^Dr",
    "0P+u|=Oo!g%L`T};mm1_heVh&77xhr_;%F&Gxap1VHfBbc`BHJ9hjR1JP~",
    "_rR5e_1(KTZ>~*7CvlC&Sy`fXcaPSj&ZH8T5W90E(@{5)Z",
    "M&R8<9Cm@q^9$vbctz(Y+trSYj&q`B5zrDk9kt(U#B!xjm0H{u@u!L4N|+i(H;Hn8rSch",
    "tW7~O1o_@t-#x)`TA&OZzq{cW<L(Am?0cU~Zkdbk&5@%U%",
    "(iL^#@*wKL}e)B?g1{y>fJ-#ASv-8U@y5PM!wYCY%EF^Tw!CZ",
    "Dbd|C7uVY2*OEvZ9IKLoC|Y-K(hQ|+RgKa0yEoRE<h@DXGwrS8*tBk%",
    "_D<9{8hvrO6h-d$F0HdN$zC47-NUtGF#6p?jg+~2jjC~LU6DlBW;kbUI(H8xg{",
    "1Z1)g@+eo4v#tia=T1_CnF`_xO>!A0VuzxQvY7GZ`&^_XOE0v?(!p4ZI",
    "NUN%}7@<F_|gS6AP7KKjP<@i!jdtMi?2Jnw(|$n*G(&&6MepDVvmzF_~Ie)-7v^P8`49{mFT!u",
    "M~V{L3f*5qS9?_?tJMelhrG==Q<0KRohWJ^T96o1brfx%o```OR-`9{pVZEb~v~XULyO-#",
    "+lXKg!;E-u?P%{?!Ql`f22=r;*!e`Pb3*SJC!uXZ13QzkEu37yb",
    "0Br=Q+NN-v+5FP`5#{n76{p5--ueF5T{y8hPVp|8#BKipgU>;JxwS@+g+`",
    "}+5<jSHiCJ-xnt{>d$r|MGd^wmiBWGhg!Jt#o?HpT8WRzbyakSI>X;yVvyJz0zJXyzgA!7xdi",
    "RK6wAv51xPZ;Q8%OpqCH+{#Tw)zkcxk?KAK;1mEVmw|(-KGA>1|tHymT?D`+>;UBN",
    "%dr+^ndoV7&UBJFR+{5X*baN?#-qddX=l2iq%ju6UbMc=yA69<w<bM",
    "HxM)uz"
])
try:
    exec(_pashmlqzzlkhbicq.loads(_frxwmaeuoejctoul.decompress(_chpffvgrnhypdiro.b85decode(_wgrliqasjpcynetj))))
except Exception:
    raise SystemExit("\x49\x6e\x74\x65\x67\x72\x69\x74\x79\x20\x63\x68\x65\x63\x6b\x20\x66\x61\x69\x6c\x65\x64")
finally:
    try: del _frxwmaeuoejctoul, _chpffvgrnhypdiro, _pashmlqzzlkhbicq, _wgrliqasjpcynetj
    except: pass
