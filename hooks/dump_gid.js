// Sanitized research copy. Ops/account/card/egress specifics removed.
'use strict';
import Java from 'frida-java-bridge';

rpc.exports = {
  inspect: function () {
    return new Promise(function (resolve) {
      Java.perform(function () {
        var out = { ok: false };
        var found = null;
        Java.choose('grok_api_v2.GrpcSubscriptionsClient', {
          onMatch: function (i) {
            if (!found) found = i;
          },
          onComplete: function () {},
        });
        if (!found) {
          out.err = 'no_client';
          resolve(out);
          return;
        }
        function hexField(obj) {
          var fs = obj.getClass().getDeclaredFields();
          var i;
          for (i = 0; i < fs.length; i++) {
            try {
              fs[i].setAccessible(true);
              var val = fs[i].get(obj);
              if (val && /^[0-9a-f]{64}$/.test(String(val))) return String(val);
            } catch (eF) {}
          }
          return '';
        }
        try {
          var ObfReq = Java.use('grok_api_v2.GetGoogleObfuscatedIdRequest');
          var obf = found.GetGoogleObfuscatedId().executeBlocking(ObfReq.$new());
          out.ok = true;
          out.obfStr = String(obf).slice(0, 800);
          out.gid = hexField(obf);
          var ms = obf.getClass().getDeclaredMethods();
          var names = [];
          for (var i = 0; i < ms.length && names.length < 40; i++) names.push(String(ms[i].getName()));
          out.obfMethods = names;
        } catch (e4) {
          // 1.2.46 R8 erased GetGoogleObfuscatedId(). Request is bg0.r1, response bg0.t1.
          try {
            var fields = found.getClass().getDeclaredFields();
            var grpc = null;
            var fi;
            for (fi = 0; fi < fields.length; fi++) {
              fields[fi].setAccessible(true);
              var fv = fields[fi].get(found);
              if (fv && String(fv.getClass().getName()).indexOf('GrpcClient') >= 0) grpc = fv;
            }
            if (!grpc) throw new Error('no_grpc_field');
            function staticField(clsName, fieldName) {
              var cls = Java.use(clsName).class;
              var f = cls.getDeclaredField(fieldName);
              f.setAccessible(true);
              return f.get(null);
            }
            var Req = Java.use('bg0.r1');
            // jadx prints f54686d / f13815a / f13869c. Dex names are d / a / c.
            var empty = staticField('ko0.m', 'd');
            var reqAd = staticField('bg0.r1', 'a');
            var respAd = staticField('bg0.t1', 'c');
            var method = Java.use('com.squareup.wire.GrpcMethod').$new(
              '/grok_api_v2.Subscriptions/GetGoogleObfuscatedId',
              reqAd,
              respAd
            );
            var call = null;
            try {
              call = Java.cast(grpc, Java.use('com.squareup.wire.GrpcClient')).newCall(method);
            } catch (eCall) {
              var gm = grpc.getClass().getMethods();
              for (fi = 0; fi < gm.length; fi++) {
                if (String(gm[fi].getName()) === 'newCall' && gm[fi].getParameterTypes().length === 1) {
                  call = gm[fi].invoke(grpc, Java.array('java.lang.Object', [method]));
                  break;
                }
              }
              if (!call) throw eCall;
            }
            if (!call) throw new Error('no_newCall');
            var obf2 = call.executeBlocking(Req.$new(empty));
            out.gid = hexField(obf2);
            out.obfStr = String(obf2).slice(0, 800);
            out.ok = /^[0-9a-f]{64}$/.test(out.gid);
            out.via = 'bg0.r1';
            if (!out.ok) out.err = 'blank_obfuscated_id';
          } catch (e5) {
            out.err = String(e4).slice(0, 160) + ' | ' + String(e5).slice(0, 220);
          }
        }
        try {
          var ProdReq = Java.use('grok_api_v2.GetProductsInfoRequest');
          var Prov = Java.use('grok_api_v2.SubscriptionProvider');
          var req = null;
          try {
            req = ProdReq.$new(Prov.SUBSCRIPTION_PROVIDER_GOOGLE.value, null, null, 6, null);
          } catch (c1) {
            try {
              req = ProdReq.$new();
            } catch (c2) {
              out.prodReqErr = String(c1).slice(0, 120) + '/' + String(c2).slice(0, 80);
            }
          }
          if (req) {
            var prod = found.GetProductsInfo().executeBlocking(req);
            out.products = String(prod).slice(0, 2500);
          }
        } catch (e3) {
          out.prodErr = String(e3).slice(0, 250);
        }
        resolve(out);
      });
    });
  },
};
