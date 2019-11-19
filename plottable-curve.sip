/** PyQt5 binding for QCustomPlot v2.0.0
 *
 *  Authors: Dmitry Voronin, Giuseppe Corbelli
 *  License: MIT
 *
 *  QCustomPlot author: Emanuel Eichhammer
 *  QCustomPlot Website/Contact: http://www.qcustomplot.com
 */


class QCPCurveData
{
%TypeHeaderCode
#include <QCustomPlot/src/plottables/plottable-curve.h>
%End
public:
  QCPCurveData();
  QCPCurveData(double t, double key, double value);

  double sortKey() const;
  static QCPCurveData fromSortKey(double sortKey);
  static bool sortKeyIsMainKey();

  double mainKey() const;
  double mainValue() const;

  QCPRange valueRange() const;

  double t;
  double key;
  double value;

  // Not present in C++
  bool operator==(const QCPCurveData &other) const;
%MethodCode
    // Not the best equality check, admitted
    sipRes = (sipCpp->t == a0->t) && (sipCpp->key && a0->key) && (sipCpp->value == a0->value);
%End
};


typedef QCPAbstractPlottable1D<QCPCurveData> QCPAbstractPlottable1D_QCPCurveData;
typedef QCPDataContainer<QCPCurveData> QCPCurveDataContainer;
typedef QCPDataContainerIterator<QCPCurveData> QCPCurveDataContainerIterator;


class QCPCurve : public QCPAbstractPlottable1D_QCPCurveData
{
%TypeHeaderCode
#include <QCustomPlot/src/qcp.h>

typedef QCPAbstractPlottable1D<QCPCurveData> QCPAbstractPlottable1D_QCPCurveData;
%End
public:
  enum LineStyle { lsNone  ///< No line is drawn between data points (e.g. only scatters)
                   ,lsLine ///< Data points are connected with a straight line
                 };

  // Ownership acquired by QCustomPlot tied to the axis
  explicit QCPCurve(QCPAxis *keyAxis, QCPAxis *valueAxis) /Transfer/;
  virtual ~QCPCurve();

  // getters:
  QCPCurveDataContainer *data();
%MethodCode
    sipRes = sipCpp->data().data();
%End
  QCPScatterStyle scatterStyle() const;
  int scatterSkip() const;
  LineStyle lineStyle() const;

  // setters:
  void setData(QCPCurveDataContainer* data);
%MethodCode
    sipCpp->setData(QSharedPointer<QCPCurveDataContainer>(a0));
%End
  void setData(const QVector<double> &t, const QVector<double> &keys, const QVector<double> &values, bool alreadySorted=false);
  void setData(const QVector<double> &keys, const QVector<double> &values);
  void setScatterStyle(const QCPScatterStyle &style);
  void setScatterSkip(int skip);
  void setLineStyle(LineStyle style);

  // non-property methods:
  void addData(const QVector<double> &t, const QVector<double> &keys, const QVector<double> &values, bool alreadySorted=false);
  void addData(const QVector<double> &keys, const QVector<double> &values);
  void addData(double t, double key, double value);
  void addData(double key, double value);

  // reimplemented virtual methods:
  virtual double selectTest(const QPointF &pos, bool onlySelectable, QVariant *details=0) const;
  virtual QCPRange getKeyRange(bool &foundRange, QCP::SignDomain inSignDomain=QCP::sdBoth) const;
  virtual QCPRange getValueRange(bool &foundRange, QCP::SignDomain inSignDomain=QCP::sdBoth, const QCPRange &inKeyRange=QCPRange()) const;

  //! This is not in QCustomPlot, but I found it handy
  Q_SLOT void setSelected(bool selected);
%MethodCode
    Py_BEGIN_ALLOW_THREADS
    QCPDataSelection current_selection = sipCpp->selection();
    if (a0)
        current_selection += sipCpp->data()->dataRange();
    else
        current_selection.clear();

    sipCpp->setSelection(current_selection);
    Py_END_ALLOW_THREADS
%End
};
