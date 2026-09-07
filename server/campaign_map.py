"""Stock retail ``MetaAssets/Multi.mvm`` converted to client wire records."""

import base64
import hashlib
import zlib

WIDTH = 51
HEIGHT = 34
RECORD_SIZE = 11
SOURCE_NAME = "Multi.mvm"
SOURCE_SHA256 = "b1de93eff01c6570a25e36eebead1f09c0c4fd0ab26affaba764b00a351c1f52"
SHA256 = "4f5dbf1c8c7fe0d92fa65c378748cb37733dc1cec6afda9befd2828e9b41afb5"

_COMPRESSED_BASE85 = (
    "c-rloy;9>a5XX0enSrfRxN(!o42>Ha8XAhwP*c;;@F01-d#rO5AChfZTCG-&14p%^k>%L?(|<o??(YGh0-)Qk`>QjLaQd5_aC4Jn"
    "V!v2uF2ZhSM~Q7>Lz2s^iSY4}x5Ds&Qbq@+o(pTqWe9D%FlW>EfORrlS!UE(BwHc>#^3t_UtWp>bKR!@m1Ge$t47u>&(G|2u?azd"
    "RvZzEV!xnU>Xib6@bGYD8g*Mlf}&4>^^a8zgicdeq+Bdt<WVwM!KOZ4$dBG4s<a}Lf};qXy#59?Qhm%s<jOeKn1^8bAljznGaHIb"
    "i0}FE3PTThp{?nECblRrTMf7pH7dbuD0hV)<>L)p{5LEGOhYoFg!D0U+9RxVA1j!5FnABIuh+0IsE{zt-NN+p1}1hfYc$$Z(wnFB"
    "z;~H%)N3NPyO{}zz-)9<i9U=wz}&%=6e}hAa%kP{m_0iYa{>&52aZXpmz~(TRGG@IA)Vk8h(oowgh4#-x5o!}`=3Y0D|kj{&Cy#&"
    "i2Dt_z+`I)hZ14~6I3I%x!L573PWA*Zflx1={R<3&P|}C73P>c04OK{!sBCx5`=gl9kI!v<n;O+2!bYSZpv>6IyTKDg~fvJH!2Eq"
    "T0-T64@uZzMW>06P00TqB`*ZTCTbq8!oZx4W+j(p$BVSsLWQ#x<4sku;Y&rB9douQz$nHJ;!_(_4c_PxKtWc@<*AfO$!UuW=k9GZ"
    "J)5KljD|@W!0fFz_dLgjDM9%B)C)fAz=$#<PReET(Wwk2loY5uz&LrT-_*=uoG2nLR*C@A$?H=p8h5-ToyvzKue%$KBxeW=tFV#j"
    "&TMAGE;UTcc2$9@_}w(bh7uHpl5&^=rIGnWC^}bErcPe<0W@Ug>uXV97`ihA=3h3*teVXxlgF%m-(Bp@MG9z2Fmt2RAoomY)O1wm"
    "CN5d5522kGQU@5m*svpx`9hEzhh(N{G3&*wIzJW8uY9cEx@QX?Aice5w(|lLj`kQ~USY&}2_v%+B`%cRm!k-MZL3*3*)S9Fyu1ja"
    "<(fL2{5K^T8PBc8AQCrmF~X$UvgP+|&gRx8BU|7EDp_l_(Nd$z{>Tav#YQ#Ljdkm0BTo3Tr*@<;2c>kTc-`%$9lM>{?&efq-jmE}"
    "##DhQv)O|D0EsmFauin>=Oc~9C^6ArC}Ni{iY3A{1U#fATaY`JVjUNaT6!9t#C@2Qe1|g6ojieR14@U+ie2GSr$&@*uI%8Nl+qbz"
    "!akIw`+&JsE0~hY-z7V6q<O+LJ_LvZQ$bo;-L}~+nRNR0Ad(>7Q8G^-wzkmaeU&EqLIv^ty)+t`3gZA%!Aic8$*t#EG1jjHDd)!y"
    "Fj;3lh~2;4i)2OVsEB9&0oN>$^bX7Q1*2ZljU6A4*b#ogw(PeDp%qLgGCy1K1G5-L8YNekN~rdYMlbaUKC>t#>k2*`G_DpS&F=<l"
    "A0>rk#r)II#VOH7<5$DAtT#(jB6s0mT8ftg"
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
