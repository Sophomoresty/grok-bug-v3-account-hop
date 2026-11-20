// Sanitized research copy. Ops/account/card/egress specifics removed.
'use strict';
import Java from 'frida-java-bridge';

var PKG = 'ai.x.grok';
var TOKEN = 'REDACTED-PURCHASE-TOKEN-PLACEHOLDER'; // real token removed; caller rewrites `var TOKEN = '...'` at compile time

rpc.exports = {
  fire: function () {
    return new Promise(function (resolve) {
      Java.perform(function () {
        try {
          var Intent = Java.use('android.content.Intent');
          var ctx = Java.use('android.app.ActivityThread').currentApplication().getApplicationContext();
          var Conn = Java.registerClass({
            name: 'com.local.Ack902_' + Math.floor(Math.random() * 1e6),
            implements: [Java.use('android.content.ServiceConnection')],
            methods: {
              onServiceConnected: function (name, service) {
                try {
                  var Binder = Java.use('android.os.IBinder');
                  var raw = Java.cast(service, Binder);
                  var Parcel = Java.use('android.os.Parcel');
                  var Bundle = Java.use('android.os.Bundle');
                  var extra = Bundle.$new();
                  extra.putString('playBillingLibraryVersion', '9.1.0');
                  extra.putBoolean('enablePendingPurchases', true);
                  var data = Parcel.obtain();
                  var reply = Parcel.obtain();
                  data.writeInterfaceToken('com.android.vending.billing.IInAppBillingService');
                  data.writeInt(9);
                  data.writeString(PKG);
                  data.writeString(TOKEN);
                  data.writeInt(1);
                  extra.writeToParcel(data, 0);
                  var ok = raw.transact(902, data, reply, 0);
                  var rec = { ok: ok };
                  try { reply.readException(); rec.ex = 'none'; } catch (e0) { rec.ex = String(e0).slice(0, 180); }
                  try {
                    var has = reply.readInt();
                    rec.hasBundle = has;
                    if (has === 1) {
                      var b = Bundle.CREATOR.createFromParcel(reply);
                      rec.rc = b.getInt('RESPONSE_CODE');
                      rec.debug = String(b.getString('DEBUG_MESSAGE') || '');
                      rec.keys = [];
                      var ks = b.keySet().iterator();
                      while (ks.hasNext()) rec.keys.push(String(ks.next()));
                    } else {
                      try { rec.rcInt = reply.readInt(); } catch (e1) { rec.rcIntErr = String(e1).slice(0, 80); }
                    }
                  } catch (e2) { rec.parse = String(e2).slice(0, 200); }
                  data.recycle();
                  reply.recycle();

                  var fd = Java.cast(Java.use('com.google.android.gms.internal.play_billing.e').T1(service), Java.use('com.google.android.gms.internal.play_billing.d'));
                  var pb = fd.e2(PKG, 'subs', null);
                  var dl = pb.getStringArrayList('INAPP_PURCHASE_DATA_LIST');
                  rec.after = [];
                  if (dl) {
                    var it = dl.iterator();
                    while (it.hasNext()) rec.after.push(String(it.next()).slice(0, 500));
                  }
                  resolve(rec);
                } catch (e) {
                  resolve({ err: String(e).slice(0, 400) });
                }
              },
              onServiceDisconnected: function () {},
              onNullBinding: function () { resolve({ err: 'null-binding' }); },
              onBindingDied: function () { resolve({ err: 'binding-died' }); }
            }
          });
          var itn = Intent.$new('com.android.vending.billing.InAppBillingService.BIND');
          itn.setPackage('com.android.vending');
          ctx.bindService(itn, Conn.$new(), 1);
        } catch (e) {
          resolve({ outer: String(e) });
        }
      });
    });
  }
};
