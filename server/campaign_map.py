"""Observed static campaign-map baseline from a live SFC3 Dynaverse session.

The wire capture contained 1,015 compact 11-byte ``tClientHex`` records for the
35x29 Generations At War 2.1 map.  This fixture preserves only that decoded map
snapshot; it contains no account, character, address, or session data.
"""

import base64
import hashlib
import zlib


WIDTH = 35
HEIGHT = 29
RECORD_SIZE = 11
SHA256 = "f3029105444106949eaf4a5a0f792dd1f3596196df2b3e998d0956866f8e5370"

_COMPRESSED_BASE85 = (
    "c-pmETW;Gh5F`~hww2f-SfX%?KoHU*KShH=C(vPh5FNdiD885EQd0jW#G15c_Qho=C4?LZ5#mmFfe)0oy@9LW+xz(}VN+{(F;E!DB|H&l)v`SYwiCS8cS0m=g@z)46@gawfz1TR`LC_4Q}XwYr~19M4HPA>HN^VNnf#LT>L9<b2LoB;4$~pz*{r@8$Uw0UHAGa~CYhw9zx%5vg15DZVkE|I@AJ!|y3wyOu>hikA<Fk^$*&~<Otpp&C+HI);tAl2_4FhmaSRkYuq-#EuhUozQCC=i$+y;9J-Dn>3A^c(UuK84^?qij=|eFY!ob&g!46H_VDvR+pzW&z6=&4Icg-Yy)2!25MgR$mQ_!TFf}JR2Qhpt7V6hgqgp~&wcv@DslGQ6H?5mT{0IEOQe6&1BrC2T2_%9D!d6fVXJ_kg3!m@Syikuca7a|w1&fgH_fYQMY1|aeK0`Oci7X@|GO6Gl!r=+9?@Z4#~M7;Ssu-p+`3qUdT0^7sTk2b^373EQRSu8baY3bnqDFR>vON-iB4g09L7CYyilEP{W(B-tK2uZjcrgX?=4@WiiP7}Fa8Q#oPhNVi+#+DXui5_M>43k2v96%kDgdCKGIa(Z#%dcox`7igWrlomOer$}3bq34VlM^B+-`TOXT-BE-s=1h8wbU%N8o+KbKy;+YaAJPtwOAkHJX~;n^<Y*9Xfumy7?$+l8P=nu$}(dFkXoq02Vi@Vu+s+AlO@|qGznQol<fgrwXXI}ob{r(uwYJ22risWSB;ba^WbBKmF9PL&!nv!z9@JSQ09Uo;MtT8o^$Xf=ZGwKF<${s7%ezn08L*7LYGOoI!{La3TTI`fW&fz1z4}qZL=cP51bb;@n>&!D?9UDJ_fJ@2Sa00d~JNam%d(QDucc6Ad{FA(x|})C7(T1#^L6Pn~(kJH~6}L#Hrr5IkoC$)YmOIGbIg1s~k`RO~FoR!Nu0njJuEqDQH<8NEz!ZuSS?F!SSeX<LMgkd3RUG=*KAe3Dy7xrl9QieL+oJ;QMCKL}HsV3XN~}6d*`Je%=`qvhbXN+xmnC^jiyM<<Qp|Su?#IygoI>I)h22Yv*SxONXy<wBsK$tV6P(dS$l$_2ElySagYLTvgip6co7R$o33|uCQgbUD*npAg|*hwkfzk*THH>5aY3We*T%?P#$lg>Lti!{Q;HBEvwTA$x^70)Du`bs`%s-`3zQ(jV}u2mv|nC)kQC2XY<nbqt);*v94oNts1IP5L0Gg0X7frQsc2r7srwzs&)Mx<1Ope2yiu2bBFbm0CQgr2ynwS4TXs*SuX~R)5fxL>W-cru;DcJZ&doJQ}O!*us-vPjsU(T1+jRtxuPzaaFAtliQO0u9xTo~_RJ>z3S;e{_<d_V0lIh!;t4I7sSM0363Axykf{N-STHPkT!1TN2TrL5{1HKuWBp&nOsceH28vkTaRu-yZ&;dP=ojpgK58ccklodmf2Pn803`GG781ax+FzZBT3LiAcp^yyeVP>_3VyVEKd<F)9Ub`S=3ht~(5q*D<q!IXaAg3(mAA=tK|EKFSK2Oc8HBBmmSV`j|GSb@&p~!E?%ARFrR4V=Z`<FoT@V_2<sh4*@)c)$oyWYRs~`W-qUd8Lfv{x?2)lAA?Br(u07P7eD*"
)


def _load_records() -> bytes:
    records = zlib.decompress(base64.b85decode(_COMPRESSED_BASE85))
    expected_length = WIDTH * HEIGHT * RECORD_SIZE
    if len(records) != expected_length:
        raise RuntimeError(f"campaign map has {len(records)} bytes, expected {expected_length}")
    if hashlib.sha256(records).hexdigest() != SHA256:
        raise RuntimeError("campaign map checksum mismatch")
    return records


CLIENT_HEX_RECORDS = _load_records()
