// Sanitized research copy. Ops/account/card/egress specifics removed.
'use strict';
import Java from 'frida-java-bridge';

var PKG = 'ai.x.grok';
var SKU = 'grok.ultra';
var GID = 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef'; // placeholder; billing_core.patch_gid rewrites this at compile time
var FORCE_ACCOUNT_ID = '';
var WANT_P3M = true;
var WANT_G4 = false;
var WANT_FROM_LITE = false;
var WANT_FIRST_G4_EXTRAS = false;
var SKIP_ACCOUNT_ID = false;
var WANT_DEFERRED = false;
var HOP_PROFILE_ID = '';
var HOP_XTID = '';
var HOP_OLD_PURCHASE_ID = '';
var FALLBACK_LITE_TOKEN = '';
var FALLBACK_ULTRA_TOKEN = '';

function parseOffers(jo) {
  var offers = [];
  if (!jo.has('subscriptionOfferDetails')) return offers;
  var arr = jo.getJSONArray('subscriptionOfferDetails');
  for (var i = 0; i < arr.length(); i++) {
    var o = arr.getJSONObject(i);
    var oid = o.has('offerId') && !o.isNull('offerId') ? String(o.getString('offerId')) : '';
    var rec = {
      offerId: oid || 'regular-p1m',
      offerIdToken: o.getString('offerIdToken'),
    };
    try {
      var phases = o.getJSONArray('pricingPhases').getJSONObject(0);
      rec.price = phases.has('formattedPrice') ? String(phases.getString('formattedPrice')) : '';
      rec.micros = phases.has('priceAmountMicros') ? String(phases.getLong('priceAmountMicros')) : '';
      rec.billing = phases.has('billingPeriod') ? String(phases.getString('billingPeriod')) : '';
    } catch (eP) {}
    offers.push(rec);
  }
  return offers;
}

function pickOffer(offers) {
  var i;
  var id;
  if (WANT_P3M) {
    // fromlite may2026 renders Starting Oct 25 $99.99 and Subscribe items.
    // Prefer another heavy-p3m (churn) when replacing Lite.
    if (WANT_FROM_LITE) {
      for (i = 0; i < offers.length; i++) {
        id = String(offers[i].offerId);
        if (id.indexOf('heavy-p3m') >= 0 && id.indexOf('may2026') < 0) return offers[i];
      }
    }
    for (i = 0; i < offers.length; i++) {
      if (String(offers[i].offerId).indexOf('heavy-p3m') >= 0) return offers[i];
    }
    for (i = 0; i < offers.length; i++) {
      if (String(offers[i].offerId).indexOf('p3m') >= 0) return offers[i];
    }
  }
  for (i = 0; i < offers.length; i++) {
    if (offers[i].offerId === 'regular-p1m') return offers[i];
  }
  return offers.length ? offers[0] : null;
}

function bindAndRun(handler) {
  return new Promise(function (resolve) {
    Java.perform(function () {
      try {
        var Intent = Java.use('android.content.Intent');
        var ctx = Java.use('android.app.ActivityThread').currentApplication().getApplicationContext();
        var Conn = Java.registerClass({
          name: 'com.local.HeavyWall' + Date.now(),
          implements: [Java.use('android.content.ServiceConnection')],
          methods: {
            onServiceConnected: function (name, service) {
              var out = { ok: false };
              try {
                var fd = Java.cast(
                  Java.use('com.google.android.gms.internal.play_billing.e').T1(service),
                  Java.use('com.google.android.gms.internal.play_billing.d')
                );
                handler(fd, out, service);
              } catch (e) {
                out.err = String(e);
              }
              resolve(out);
            },
            onServiceDisconnected: function () {},
            onNullBinding: function () {
              resolve({ ok: false, err: 'null_binding' });
            },
            onBindingDied: function () {},
          },
        });
        var intent = Intent.$new('com.android.vending.billing.InAppBillingService.BIND');
        intent.setPackage('com.android.vending');
        var ok = ctx.bindService(intent, Conn.$new(), 1);
        if (!ok) resolve({ ok: false, err: 'bind_false' });
      } catch (e) {
        resolve({ ok: false, outer: String(e) });
      }
    });
  });
}

function inspectFd(fd, out) {
  var Bundle = Java.use('android.os.Bundle');
  var AL = Java.use('java.util.ArrayList');
  var JSONObject = Java.use('org.json.JSONObject');
  out.purchases = [];
  try {
    var pb = fd.e2(PKG, 'subs', null);
    out.e2rc = pb.getInt('RESPONSE_CODE');
    var dlist = pb.getStringArrayList('INAPP_PURCHASE_DATA_LIST');
    if (dlist) {
      var it = dlist.iterator();
      while (it.hasNext()) {
        var js = String(it.next());
        var rec = { rawHead: js.slice(0, 280), raw: js };
        try {
          var joP = JSONObject.$new(js);
          rec.productId = joP.has('productId') ? String(joP.getString('productId')) : '';
          rec.tokenHead = joP.has('purchaseToken') ? String(joP.getString('purchaseToken')).slice(0, 24) : '';
          rec.orderId = joP.has('orderId') ? String(joP.getString('orderId')) : '';
          rec.autoRenewing = joP.has('autoRenewing') ? joP.getBoolean('autoRenewing') : null;
          rec.obfHead = joP.has('obfuscatedAccountId')
            ? String(joP.getString('obfuscatedAccountId')).slice(0, 16)
            : '';
          rec.purchaseToken = joP.has('purchaseToken') ? String(joP.getString('purchaseToken')) : '';
          rec.obfuscatedAccountId = joP.has('obfuscatedAccountId')
            ? String(joP.getString('obfuscatedAccountId'))
            : '';
        } catch (eJ) {
          rec.parseErr = String(eJ);
        }
        out.purchases.push(rec);
      }
    }
  } catch (e2) {
    out.e2err = String(e2);
  }

  var skuB = Bundle.$new();
  var ids = AL.$new();
  ids.add(SKU);
  skuB.putStringArrayList('ITEM_ID_LIST', ids);
  var extra = Bundle.$new();
  extra.putString('playBillingLibraryVersion', '9.1.1');
  extra.putString('SKU_DETAILS_RESPONSE_FORMAT', 'PRODUCT_DETAILS');
  extra.putBoolean('enablePendingPurchases', true);
  var multi = AL.$new();
  multi.add('subs');
  extra.putStringArrayList('PRODUCT_TYPES_TO_RETURN_MULTIPLE_OFFERS', multi);
  extra.putBoolean('SHOULD_RETURN_UNFETCHED_PRODUCTS', true);
  var r = fd.g2(21, PKG, 'subs', skuB, extra);
  out.g2rc = r.getInt('RESPONSE_CODE');
  var details = r.getStringArrayList('DETAILS_LIST');
  out.offers = [];
  out.skuTok = null;
  if (details && !details.isEmpty()) {
    var row = String(details.get(0));
    out.rowHead = row.slice(0, 280);
    var jo = JSONObject.$new(row);
    out.skuTok = jo.getString('skuDetailsToken');
    out.offers = parseOffers(jo);
  }
  return { Bundle: Bundle, AL: AL, JSONObject: JSONObject };
}

function putReplaceProto(extras, AL, oldSku, newSku, modeArg) {
  var t1 = Java.use('com.google.android.gms.internal.play_billing.t1');
  var m1c = Java.use('com.google.android.gms.internal.play_billing.m1');
  var o1c = Java.use('com.google.android.gms.internal.play_billing.o1');
  var newB = t1.p();
  newB.e('subs:ai.x.grok:' + newSku);
  var oldB = t1.p();
  oldB.e('subs:ai.x.grok:' + oldSku);
  var lb = m1c.p();
  lb.e(newB);
  lb.f(oldB);
  lb.g(modeArg);
  var ral = Java.use('java.util.ArrayList').$new();
  ral.add(lb.a());
  var ob = o1c.p();
  ob.e(ral);
  var bytes = ob.a().b();
  extras.putByteArray('subscriptionProductReplacementParamsList', bytes);
  return bytes.length;
}

function ack902(service, token, out) {
  try {
    var Binder = Java.use('android.os.IBinder');
    var raw = Java.cast(service, Binder);
    var Parcel = Java.use('android.os.Parcel');
    var Bundle = Java.use('android.os.Bundle');
    var extra = Bundle.$new();
    extra.putString('playBillingLibraryVersion', '9.1.1');
    extra.putBoolean('enablePendingPurchases', true);
    var data = Parcel.obtain();
    var reply = Parcel.obtain();
    data.writeInterfaceToken('com.android.vending.billing.IInAppBillingService');
    data.writeInt(9);
    data.writeString(PKG);
    data.writeString(token);
    data.writeInt(1);
    extra.writeToParcel(data, 0);
    out.ackTransact = raw.transact(902, data, reply, 0);
    try {
      reply.readException();
      out.ackEx = 'none';
    } catch (e0) {
      out.ackEx = String(e0).slice(0, 120);
    }
    data.recycle();
    reply.recycle();
  } catch (eAck) {
    out.ackErr = String(eAck).slice(0, 160);
  }
}

function sendBuy(fd, Bundle, AL, out, skuTok, offer, replace) {
  var ex = Bundle.$new();
  ex.putBoolean('enablePendingPurchases', true);
  ex.putString('playBillingLibraryVersion', '9.1.1');
  var ot = AL.$new();
  ot.add(offer.offerIdToken);
  var st = AL.$new();
  st.add(skuTok);
  ex.putStringArrayList('SKU_OFFER_ID_TOKEN_LIST', ot);
  ex.putStringArrayList('skuDetailsTokens', st);
  var accountId = GID;
  // fromlite: Lite d2 写的是 extras.accountId=GID. Play 收据 obfuscatedAccountId
  // 可以不同 (G1 2026-09-13: GID <gid16-a> vs receipt <gid16-b>). 用收据 obf replace →
  // Acquire "item you requested is not available". leftover g4 仍用收据 obf.
  if (replace && replace.accountId && !WANT_FROM_LITE) accountId = replace.accountId;
  if (FORCE_ACCOUNT_ID) accountId = FORCE_ACCOUNT_ID;
  if (SKIP_ACCOUNT_ID) {
    out.accountId = '';
    out.skipAccountId = true;
  } else {
    ex.putString('accountId', accountId);
    out.accountId = String(accountId).slice(0, 16);
  }
  if (HOP_PROFILE_ID) {
    ex.putString('obfuscatedProfileId', HOP_PROFILE_ID);
    out.hopProfile = String(HOP_PROFILE_ID).slice(0, 16);
  }
  if (HOP_XTID) {
    ex.putString('originalExternalTransactionId', HOP_XTID);
    out.hopXtid = String(HOP_XTID).slice(0, 24);
  }
  if (HOP_OLD_PURCHASE_ID) {
    ex.putString('oldSkuPurchaseId', HOP_OLD_PURCHASE_ID);
    out.hopOldId = String(HOP_OLD_PURCHASE_ID).slice(0, 24);
  }
  if (WANT_FIRST_G4_EXTRAS) {
    ex.putInt('replacementMode', 3);
    ex.putInt('replaceSkusProrationMode', 3);
    ex.putInt('prorationMode', 3);
    ex.putInt('playBillingLibraryReplacementMode', 3);
    out.firstG4extras = true;
  }
  out.offerId = offer.offerId;
  out.offerPrice = offer.price || '';
  if (replace && replace.token) {
    ex.putString('oldSkuPurchaseToken', replace.token);
    var olds = AL.$new();
    olds.add(replace.oldSku || SKU);
    ex.putStringArrayList('skusToReplace', olds);
    var modeArg = WANT_DEFERRED ? 6 : 4;
    var rm = WANT_DEFERRED ? 6 : 3;
    ex.putInt('replacementMode', rm);
    ex.putInt('replaceSkusProrationMode', rm);
    out.protoN = putReplaceProto(ex, AL, replace.oldSku || SKU, SKU, modeArg);
    out.replaceTokenHead = String(replace.token).slice(0, 24);
    out.modeArg = modeArg;
  }
  var bb = fd.d2(17, PKG, SKU, 'subs', ex);
  out.d2rc = bb.getInt('RESPONSE_CODE');
  try {
    out.d2msg = String(bb.getString('DEBUG_MESSAGE') || '');
  } catch (e0) {
    out.d2msg = '';
  }
  out.d2keys = String(bb.keySet());
  var pi = bb.getParcelable('BUY_INTENT');
  out.hasPI = !!pi;
  if (pi) {
    Java.cast(pi, Java.use('android.app.PendingIntent')).send();
    out.sent = true;
  }
  out.ok = out.d2rc === 0 && !!pi;
}

rpc.exports = {
  inspect: function () {
    WANT_G4 = false;
    return bindAndRun(function (fd, out) {
      inspectFd(fd, out);
      out.ok = true;
    });
  },
  p1m: function () {
    WANT_P3M = false;
    WANT_G4 = false;
    SKIP_ACCOUNT_ID = false;
    return rpc.exports.fire();
  },
  p3m: function () {
    WANT_P3M = true;
    WANT_G4 = false;
    SKIP_ACCOUNT_ID = false;
    return rpc.exports.fire();
  },
  g4: function () {
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = false;
    return rpc.exports.fire();
  },
  skipg4: function () {
    WANT_P3M = true;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = true;
    WANT_DEFERRED = false;
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    return rpc.exports.fire();
  },
  skipg4p1m: function () {
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = true;
    WANT_DEFERRED = false;
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    return rpc.exports.fire();
  },
  skipg4deferred: function () {
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = true;
    WANT_DEFERRED = true;
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    return rpc.exports.fire();
  },
  fromlite: function () {
    // G4 2026-09-26 acct: p3m Oct 25 intro and 3-month walls
    // item. regular-p1m Starting Oct 25 $299.99/month, first charge Oct 25,
    // no Today $, ultra AR then g4 new GPA and GET cap.
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = true;
    return rpc.exports.fire();
  },
  fromlitep1m: function () {
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = true;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = false;
    WANT_DEFERRED = false;
    return rpc.exports.fire();
  },
  destfromlite: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = true;
    WANT_FIRST_G4_EXTRAS = false;
    return rpc.exports.fire();
  },
  destg4: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    WANT_P3M = true;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = false;
    WANT_DEFERRED = false;
    return rpc.exports.fire();
  },
  destg4p1m: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    SKIP_ACCOUNT_ID = false;
    WANT_DEFERRED = false;
    return rpc.exports.fire();
  },
  hopprofile: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = FORCE_ACCOUNT_ID;
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return rpc.exports.fire();
  },
  hopxtid: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = '';
    HOP_OLD_PURCHASE_ID = '';
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return bindAndRun(function (fd, out) {
      var cls = inspectFd(fd, out);
      var offer = pickOffer(out.offers || []);
      if (!out.skuTok || !offer) {
        out.err = 'no_offer';
        return;
      }
      var ultra = null;
      var i;
      for (i = 0; i < (out.purchases || []).length; i++) {
        var p = out.purchases[i];
        if (p.productId === 'grok.ultra' && p.purchaseToken) {
          ultra = {
            token: p.purchaseToken,
            accountId: p.obfuscatedAccountId || GID,
            oldSku: 'grok.ultra',
            orderId: p.orderId || '',
          };
        }
      }
      if (!ultra) {
        out.err = 'no_ultra_leftover_for_g4';
        return;
      }
      HOP_XTID = ultra.orderId || ultra.token;
      sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, ultra);
    });
  },
  hopprofilealign: function (gid) {
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = typeof gid === 'string' && gid ? gid : '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    WANT_P3M = false;
    WANT_G4 = true;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return rpc.exports.fire();
  },
  hopoldidtok: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    WANT_P3M = true;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return bindAndRun(function (fd, out) {
      var cls = inspectFd(fd, out);
      var offer = pickOffer(out.offers || []);
      if (!out.skuTok || !offer) {
        out.err = 'no_offer';
        return;
      }
      var tok = '';
      var i;
      for (i = 0; i < (out.purchases || []).length; i++) {
        var p = out.purchases[i];
        if (p.productId === 'grok.ultra' && p.purchaseToken) tok = p.purchaseToken;
      }
      if (!tok) {
        out.err = 'no_ultra_token';
        return;
      }
      HOP_OLD_PURCHASE_ID = tok;
      sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, null);
    });
  },
  hopoldidonly: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    WANT_P3M = true;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return bindAndRun(function (fd, out) {
      var cls = inspectFd(fd, out);
      var offer = pickOffer(out.offers || []);
      if (!out.skuTok || !offer) {
        out.err = 'no_offer';
        return;
      }
      var orderId = '';
      var i;
      for (i = 0; i < (out.purchases || []).length; i++) {
        var p = out.purchases[i];
        if (p.productId === 'grok.ultra' && p.orderId) orderId = p.orderId;
      }
      if (!orderId) {
        out.err = 'no_ultra_order_id';
        return;
      }
      HOP_OLD_PURCHASE_ID = orderId;
      sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, null);
    });
  },
  hopxtidonly: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : '';
    GID = FORCE_ACCOUNT_ID || GID;
    HOP_PROFILE_ID = '';
    HOP_OLD_PURCHASE_ID = '';
    WANT_P3M = true;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return bindAndRun(function (fd, out) {
      var cls = inspectFd(fd, out);
      var offer = pickOffer(out.offers || []);
      if (!out.skuTok || !offer) {
        out.err = 'no_offer';
        return;
      }
      var orderId = '';
      var i;
      for (i = 0; i < (out.purchases || []).length; i++) {
        var p = out.purchases[i];
        if (p.productId === 'grok.ultra' && p.orderId) orderId = p.orderId;
      }
      if (!orderId) {
        out.err = 'no_ultra_order_id';
        return;
      }
      HOP_XTID = orderId;
      sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, null);
    });
  },
  ultranogid: function () {
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    SKIP_ACCOUNT_ID = true;
    WANT_P3M = false;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return rpc.exports.fire();
  },
  p3mnogid: function () {
    FORCE_ACCOUNT_ID = '';
    HOP_PROFILE_ID = '';
    HOP_XTID = '';
    HOP_OLD_PURCHASE_ID = '';
    SKIP_ACCOUNT_ID = true;
    WANT_P3M = true;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = false;
    return rpc.exports.fire();
  },
  firstg4extras: function (gid) {
    FORCE_ACCOUNT_ID = typeof gid === 'string' && gid ? gid : GID;
    GID = FORCE_ACCOUNT_ID || GID;
    WANT_P3M = true;
    WANT_G4 = false;
    WANT_FROM_LITE = false;
    WANT_FIRST_G4_EXTRAS = true;
    return rpc.exports.fire();
  },
  fire: function () {
    return bindAndRun(function (fd, out, service) {
      var cls = inspectFd(fd, out);
      var offer = pickOffer(out.offers || []);
      if (!out.skuTok) {
        out.err = 'no_ultra_sku_token';
        return;
      }
      if (!offer) {
        out.err = 'no_ultra_offer';
        return;
      }
      var ultra = null;
      var lite = null;
      var i;
      for (i = 0; i < (out.purchases || []).length; i++) {
        var p = out.purchases[i];
        if (p.productId === 'grok.ultra' && p.purchaseToken) {
          ultra = {
            token: p.purchaseToken,
            accountId: p.obfuscatedAccountId || GID,
            oldSku: 'grok.ultra',
            orderId: p.orderId || '',
          };
        }
        if (p.productId === 'grok.lite' && p.purchaseToken) {
          lite = {
            token: p.purchaseToken,
            accountId: p.obfuscatedAccountId || GID,
            oldSku: 'grok.lite',
          };
        }
      }
      // e2 omits a canceled grok.ultra that library.db still owns.
      if (!ultra && FALLBACK_ULTRA_TOKEN) {
        ultra = {
          token: FALLBACK_ULTRA_TOKEN,
          accountId: '',
          oldSku: 'grok.ultra',
          orderId: '',
        };
        out.ultraFromLibrary = true;
      }
      if (!lite && FALLBACK_LITE_TOKEN) {
        lite = {
          token: FALLBACK_LITE_TOKEN,
          accountId: GID,
          oldSku: 'grok.lite',
        };
        out.liteFromCache = true;
      }
      var replace = null;
      if (WANT_FIRST_G4_EXTRAS) {
        sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, null);
        return;
      }
      if (WANT_FROM_LITE) {
        if (!lite) {
          out.err = 'no_lite_token_for_fromlite';
          return;
        }
        if (service && lite.token) ack902(service, lite.token, out);
        replace = lite;
      } else if (WANT_G4) {
        if (!ultra) {
          out.err = 'no_ultra_leftover_for_g4';
          return;
        }
        replace = ultra;
      }
      sendBuy(fd, cls.Bundle, cls.AL, out, out.skuTok, offer, replace);
    });
  },
};
