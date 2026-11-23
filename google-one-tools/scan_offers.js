// scan_offers.js —— Solo consulta, sin compras: devuelve todas las ofertas y fases de precios de cada SKU
// Python reemplaza la línea placeholder PRODUCTS; formato de envío:
//   {ev:"offer", product, id, token, tags:[..], phases:[{micros, cur, period, cycles, free, fmt}]}
var MODULE_APK = "/data/local/tmp/module_521.apk";
var PRODUCTS = [];   // ← Inyectado por Python

Java.perform(function () {
    var context = Java.use("android.app.ActivityThread").currentApplication().getApplicationContext();
    var ArrayList = Java.use("java.util.ArrayList");
    var List = Java.use("java.util.List");

    var DexClassLoader = Java.use("dalvik.system.DexClassLoader");
    var dexLoader = DexClassLoader.$new(MODULE_APK,
        context.getCodeCacheDir().getAbsolutePath(), null, context.getClassLoader());
    Java.classFactory.loader = dexLoader;

    var BillingClient = Java.use("com.android.billingclient.api.BillingClient");
    var QueryProductDetailsParams = Java.use("com.android.billingclient.api.QueryProductDetailsParams");
    var QpdProduct = Java.use("com.android.billingclient.api.QueryProductDetailsParams$Product");
    var PurchasesUpdatedListener = Java.use("com.android.billingclient.api.PurchasesUpdatedListener");
    var BillingClientStateListener = Java.use("com.android.billingclient.api.BillingClientStateListener");
    var ProductDetailsResponseListener = Java.use("com.android.billingclient.api.ProductDetailsResponseListener");
    var ProductDetails = Java.use("com.android.billingclient.api.ProductDetails");
    var SOD = Java.use("com.android.billingclient.api.ProductDetails$SubscriptionOfferDetails");
    var PP = Java.use("com.android.billingclient.api.ProductDetails$PricingPhase");
    var Handler = Java.use("android.os.Handler");
    var Looper = Java.use("android.os.Looper");

    function S(o) { try { send(o); } catch (e) {} }

    var pl = Java.registerClass({
        name: "com.frida.scan.PL", implements: [PurchasesUpdatedListener],
        methods: { onPurchasesUpdated: function () {} }
    }).$new();

    var bc = BillingClient.newBuilder(context).setListener(pl).enablePendingPurchases().build();

    var sl = Java.registerClass({
        name: "com.frida.scan.SL", implements: [BillingClientStateListener],
        methods: {
            onBillingSetupFinished: function (r) {
                S({ ev: "setup", code: r.getResponseCode() });
                if (r.getResponseCode() !== 0) { S({ ev: "query_err", m: "setup" }); return; }
                Java.classFactory.loader = null;
                var h = Handler.$new(Looper.getMainLooper());
                Java.classFactory.loader = dexLoader;
                var R = Java.use("java.lang.Runnable");
                h.post(Java.registerClass({
                    name: "com.frida.scan.QR", implements: [R],
                    methods: { run: function () { doQuery(); } }
                }).$new());
            },
            onBillingServiceDisconnected: function () { S({ ev: "query_err", m: "disc" }); }
        }
    }).$new();

    function doQuery() {
        var arr = ArrayList.$new();
        for (var i = 0; i < PRODUCTS.length; i++) {
            arr.add(QpdProduct.newBuilder().setProductId(PRODUCTS[i]).setProductType("subs").build());
        }
        bc.queryProductDetailsAsync(
            QueryProductDetailsParams.newBuilder().setProductList(arr).build(),
            Java.registerClass({
                name: "com.frida.scan.PDL", implements: [ProductDetailsResponseListener],
                methods: {
                    onProductDetailsResponse: function (br, pdList) {
                        onProducts(br, pdList);
                    }
                }
            }).$new());
    }

    function onProducts(br, pdList) {
        try {
            var list = Java.cast(pdList, List);
            S({ ev: "pd", code: br.getResponseCode(), n: list.size() });
            for (var i = 0; i < list.size(); i++) {
                var pd = Java.cast(list.get(i), ProductDetails);
                var pid = String(pd.getProductId());
                var title = "";
                try { title = String(pd.getTitle()); } catch (e) {}
                var offers = pd.getSubscriptionOfferDetails();
                if (offers == null) { S({ ev: "no_offers", product: pid }); continue; }
                var ol = Java.cast(offers, List);
                for (var j = 0; j < ol.size(); j++) {
                    var o = Java.cast(ol.get(j), SOD);
                    var oid = String(o.getOfferId());
                    var tok = String(o.getOfferToken());

                    var tagStr = "";
                    try {
                        var tags = Java.cast(o.getOfferTags(), List);
                        var ts = [];
                        for (var t = 0; t < tags.size(); t++) ts.push(String(tags.get(t)));
                        tagStr = ts.join(",");
                    } catch (e) {}

                    var phases = [];
                    var ph = Java.cast(o.getPricingPhases().getPricingPhaseList(), List);
                    for (var k = 0; k < ph.size(); k++) {
                        var p = Java.cast(ph.get(k), PP);
                        var micros = String(p.getPriceAmountMicros());
                        var cur = "";
                        try { cur = String(p.getPriceCurrencyCode()); } catch (e) {}
                        phases.push({
                            micros: micros, cur: cur,
                            period: String(p.getBillingPeriod()),
                            cycles: p.getBillingCycleCount(),
                            free: (micros === "0"),
                            fmt: String(p.getFormattedPrice())
                        });
                    }
                    S({ ev: "offer", product: pid, title: title, id: oid, token: tok,
                        tags: tagStr, phases: phases });
                }
            }
            S({ ev: "done" });
        } catch (e) {
            S({ ev: "query_err", m: String(e) });
        }
    }

    bc.startConnection(sl);
});
setInterval(function () {}, 1000);
